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
