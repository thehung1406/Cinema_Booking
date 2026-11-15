from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from sqlmodel import Session, select
from sqlalchemy import func
from cinema_platform.events import OutboxRecord
from review_service.models import Review, ReviewSentiment, utcnow
from review_service import service
from review_service.worker import process_one
from review_service.schemas import ReviewEdit
from test_review_api import PREDICTOR
import pytest


def make_review(engine, settings):
    settings.auto_approve = True
    with Session(engine) as db:
        return service.create_review(db, 1, 777, "Phim hay rất đáng xem", settings).id


@pytest.mark.parametrize("action", ["edit", "retry", "delete", "moderate"])
def test_old_inference_cannot_overwrite_content_or_analysis_generation(review_store, review_settings, action):
    from review_service.schemas import ModerationWrite
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
            else:
                service.moderate_review(db, rid, ModerationWrite(content_version=1, status="rejected"))
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
    (.44, .51, "needs_review", "transformers"),
])
def test_sentiment_worker_uses_fallback_only_below_threshold(
    review_store, review_settings, monkeypatch, primary_score, fallback_score, expected_status, expected_backend
):
    review_settings.sentiment_backend = "sklearn"
    review_settings.sentiment_fallback_backend = "transformers"
    review_settings.sentiment_fallback_model_path = "/models/visobert"
    rid = make_review(review_store, review_settings)
    called = []

    def load(backend, path):
        called.append(backend)
        score = primary_score if backend == "sklearn" else fallback_score
        return (lambda _: {"positive": score, "neutral": (1 - score) / 2, "negative": (1 - score) / 2}), backend

    monkeypatch.setattr("review_service.worker.load_predictor", load)
    assert process_one(review_store, review_settings) == expected_status
    assert called == (["sklearn"] if expected_backend == "sklearn" else ["sklearn", "transformers"])
    with Session(review_store) as db:
        result = db.get(ReviewSentiment, rid)
        assert result.model_version == expected_backend
        assert result.predicted_label == "positive"
        assert result.scores["positive"] == (primary_score if expected_backend == "sklearn" else fallback_score)


@pytest.mark.parametrize(("content", "enabled", "status", "source", "label"), [
    ("Phim dở quá", True, "succeeded", "rule", "negative"),
    ("Phim này rất tệ!", True, "succeeded", "rule", "negative"),
    ("Phim dở quá", False, "needs_review", "model", "positive"),
    ("Phim không dở", True, "needs_review", "model", "positive"),
    ("Phim dở quá nhưng diễn xuất tốt.", True, "needs_review", "model", "positive"),
    ("Phim dở quá?", True, "needs_review", "model", "positive"),
])
def test_literal_negative_rule_preserves_the_original_prediction(
    review_store, review_settings, content, enabled, status, source, label
):
    review_settings.auto_approve = True
    review_settings.sentiment_literal_negative_enabled = enabled
    with Session(review_store) as db:
        rid = service.create_review(db, 1, 777, content, review_settings).id
    prediction = {"positive": .44, "neutral": .26, "negative": .30}
    assert process_one(review_store, review_settings, (lambda _: prediction, "model-demo")) == status
    with Session(review_store) as db:
        result = db.get(ReviewSentiment, rid)
        assert (result.label, result.decision_source) == (label, source)
        assert result.predicted_label == "positive"
        assert result.scores == prediction


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
