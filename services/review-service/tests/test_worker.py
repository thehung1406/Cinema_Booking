from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from sqlmodel import Session, select
from sqlalchemy import func
from cinema_platform.events import OutboxRecord
from review_service.models import Review, ReviewSentiment, utcnow
from review_service.predictor import InputTooLong
from review_service import service
from review_service.worker import process_one
from review_service.schemas import ReviewEdit
from test_review_api import PREDICTOR
import pytest


def make_review(engine, settings):
    with Session(engine) as db:
        return service.create_review(db, 1, 777, "Phim hay rất đáng xem", settings).id


@pytest.mark.parametrize("action", ["edit", "retry", "delete"])
def test_old_inference_cannot_overwrite_content_or_analysis_generation(review_store, review_settings, action):
    rid = make_review(review_store, review_settings)
    def racing(text):
        with Session(review_store) as db:
            if action == "edit":
                service.edit_review(db, rid, 777, ReviewEdit(content="Đổi ý sau khi xem", content_version=1), review_settings)
            elif action == "retry":
                service.invalidate(db, service.locked_review(db, rid))
                db.commit()
            elif action == "delete":
                service.delete_review(db, rid, 777)
        return PREDICTOR[0](text)
    assert process_one(review_store, review_settings, (racing, "old-model")) == "stale"
    with Session(review_store) as db:
        result = db.get(ReviewSentiment, rid)
        assert result.status == "pending" and result.label is None and result.attempts == 0
        assert not db.exec(select(OutboxRecord).where(OutboxRecord.event_type == "ReviewSentimentUpdated.v1")).all()


def test_parallel_workers_lease_recovery_and_single_result_event(review_store, review_settings):
    rid = make_review(review_store, review_settings)
    entered, release = Event(), Event()
    def slow(text):
        entered.set()
        assert release.wait(5)
        return PREDICTOR[0](text)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(process_one, review_store, review_settings, (slow, "slow-test-model"))
        assert entered.wait(5)
        try:
            assert process_one(review_store, review_settings, PREDICTOR) is False
            # Simulate a lost lease/restart while an old computation is still running.
            with Session(review_store) as db:
                result = db.get(ReviewSentiment, rid)
                result.lease_until = utcnow()-timedelta(seconds=1)
                db.commit()
            assert process_one(review_store, review_settings, PREDICTOR) == "succeeded"
        finally:
            release.set()
        assert first.result(timeout=5) == "stale"
    with Session(review_store) as db:
        assert db.get(ReviewSentiment, rid).attempts == 2
        assert db.scalar(select(func.count()).select_from(OutboxRecord).where(OutboxRecord.event_type == "ReviewSentimentUpdated.v1")) == 1


def test_invalid_prediction_bounded_retry_manual_reset_and_disabled_backend(review_store, review_settings):
    rid = make_review(review_store, review_settings)
    assert process_one(review_store, review_settings) is False
    bad = (lambda text: {"positive": float("nan")}, "bad-model")
    for attempt in range(review_settings.max_attempts):
        assert process_one(review_store, review_settings, bad) == "failed"
        with Session(review_store) as db:
            result = db.get(ReviewSentiment, rid)
            result.updated_at = utcnow()-timedelta(seconds=review_settings.retry_seconds+1)
            db.commit()
    assert process_one(review_store, review_settings, PREDICTOR) is False
    with Session(review_store) as db:
        service.invalidate(db, service.locked_review(db, rid))
        db.commit()
    assert process_one(review_store, review_settings, PREDICTOR) == "succeeded"


@pytest.mark.parametrize(("primary_score", "fallback_score", "expected_status", "expected_backend"), [
    (.65, .80, "succeeded", "sklearn"),
    (.44, .73, "succeeded", "transformers"),
    (.44, .51, "succeeded", "transformers"),
])
def test_sentiment_worker_uses_fallback_only_below_threshold(
    review_store, review_settings, monkeypatch, primary_score, fallback_score, expected_status, expected_backend
):
    review_settings.sentiment_backend = "sklearn"
    review_settings.sentiment_fallback_backend = "transformers"
    review_settings.sentiment_fallback_model_path = "/models/visobert"
    rid = make_review(review_store, review_settings)
    called = []

    def load(backend, path, *, reject_truncation=False):
        called.append((backend, reject_truncation))
        score = primary_score if backend == "sklearn" else fallback_score
        return (lambda _: {"positive": score, "neutral": (1 - score) / 2, "negative": (1 - score) / 2}), backend

    monkeypatch.setattr("review_service.worker.load_predictor", load)
    assert process_one(review_store, review_settings) == expected_status
    assert called == ([("sklearn", False)] if expected_backend == "sklearn"
                      else [("sklearn", False), ("transformers", True)])
    with Session(review_store) as db:
        result = db.get(ReviewSentiment, rid)
        assert result.model_version == expected_backend
        assert result.predicted_label == "positive"
        assert result.scores["positive"] == (primary_score if expected_backend == "sklearn" else fallback_score)


@pytest.mark.parametrize(("error", "status"), [(InputTooLong, "succeeded"), (RuntimeError, "succeeded")])
def test_worker_preserves_primary_when_fallback_rejects_long_input(
    review_store, review_settings, monkeypatch, error, status
):
    review_settings.sentiment_fallback_backend = "transformers"
    review_settings.sentiment_fallback_model_path = "/models/visobert"
    content = "Phim dở" + "!" * 1000
    with Session(review_store) as db:
        rid = service.create_review(db, 1, 777, content, review_settings).id

    def fallback(text):
        assert text == content
        raise error

    monkeypatch.setattr("review_service.worker.load_predictor", lambda *args, **kwargs: (fallback, "visobert"))
    scores = {"positive": .44, "neutral": .26, "negative": .30}
    assert process_one(review_store, review_settings, (lambda _: scores, "primary")) == status
    with Session(review_store) as db:
        result = db.get(ReviewSentiment, rid)
        assert result.status == status
        if status == "succeeded":
            assert (result.label, result.predicted_label, result.decision_source) == ("positive", "positive", "model")
            assert result.model_version == "primary"
            assert result.scores == scores
        else:
            assert result.model_version is None
            assert result.scores == {}


@pytest.mark.parametrize(("content", "label"), [
    ("Phim dở quá", "negative"),
    ("Diễn xuất vừa phải", "neutral"),
    ("Phim không dở", "positive"),
])
def test_low_confidence_uses_highest_model_score(review_store, review_settings, content, label):
    with Session(review_store) as db:
        rid = service.create_review(db, 1, 777, content, review_settings).id
    prediction = {key: .44 if key == label else .28 for key in ('positive', 'neutral', 'negative')}
    assert process_one(review_store, review_settings, (lambda _: prediction, "model-demo")) == 'succeeded'
    with Session(review_store) as db:
        result = db.get(ReviewSentiment, rid)
        assert (result.label, result.decision_source) == (label, 'model')
        assert result.predicted_label == label
        assert result.scores == prediction


@pytest.mark.parametrize('failure', ['missing', 'inference', 'scores', 'version'])
def test_broken_optional_fallback_preserves_valid_primary(review_store, review_settings, monkeypatch, failure):
    rid = make_review(review_store, review_settings)
    review_settings.sentiment_fallback_backend = 'transformers'
    review_settings.sentiment_fallback_model_path = '/models/missing-fallback'
    primary = {'positive': .44, 'neutral': .28, 'negative': .28}

    def load(*args, **kwargs):
        if failure == 'missing':
            raise FileNotFoundError('missing artifact')
        def predict(_):
            if failure == 'inference':
                raise RuntimeError('fallback failure')
            return {'positive': 2.0} if failure == 'scores' else primary
        return predict, '' if failure == 'version' else 'fallback-model'

    monkeypatch.setattr('review_service.worker.load_predictor', load)
    assert process_one(review_store, review_settings, (lambda _: primary, 'primary-model')) == 'succeeded'
    with Session(review_store) as db:
        result = db.get(ReviewSentiment, rid)
        assert result.scores == primary and result.model_version == 'primary-model'
        assert result.label == 'positive' and result.decision_source == 'model'


def test_outbox_error_rolls_back_review_and_pending_job(review_store, review_settings, monkeypatch):
    from review_service import events
    from sqlalchemy.exc import SQLAlchemyError
    def broken(*args):
        raise SQLAlchemyError("injected outbox flush failure")
    monkeypatch.setattr(events, "enqueue", broken)
    with Session(review_store) as db:
        with pytest.raises(SQLAlchemyError):
            service.create_review(db, 1, 777, "Không được lưu một nửa", review_settings)
        db.rollback()
    with Session(review_store) as db:
        assert db.scalar(select(func.count()).select_from(Review)) == 0
        assert db.scalar(select(func.count()).select_from(ReviewSentiment)) == 0
