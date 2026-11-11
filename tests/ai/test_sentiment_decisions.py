from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, func
from sqlmodel import Session

from cinema_platform.events import MessagingBase, OutboxRecord
from review_service.models import Base, Review, ReviewSentiment, SentimentDecision, utcnow
from review_service.schemas import SentimentDecisionWrite
from review_service.service import decide_sentiment, invalidate, summaries
from review_service.config import Settings


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    MessagingBase.metadata.create_all(engine)
    with Session(engine) as db:
        stamp = utcnow() - timedelta(days=2)
        db.add(Review(id=1, user_id=2, film_id=3, content="Nội dung mẫu kiểm thử", content_version=1,
                      moderation_status="approved", is_deleted=False, event_version=0, updated_at=stamp))
        db.add(ReviewSentiment(review_id=1, content_version=1, analysis_generation=2, status="needs_review",
            label="positive", predicted_label="positive", decision_source="model",
            scores={"positive": .55, "neutral": .3, "negative": .15}, model_version="fixture", updated_at=stamp))
        db.commit()
    yield engine
    engine.dispose()


def command(db, **overrides):
    result = db.get(ReviewSentiment, 1)
    return SentimentDecisionWrite.model_validate(dict(request_id=str(uuid4()), content_version=1,
        analysis_generation=result.analysis_generation, expected_updated_at=result.updated_at.replace(tzinfo=utcnow().tzinfo),
        label="negative", reason="Human decision test fixture") | overrides)


def test_staff_decision_preserves_prediction_window_and_replays_exactly(store):
    with Session(store) as db:
        original = db.get(Review, 1).updated_at
        body = command(db)
        response = decide_sentiment(db, 1, 9, body)
        again = decide_sentiment(db, 1, 9, body)
        assert response == again
        result = db.get(ReviewSentiment, 1)
        assert result.label == "negative" and result.predicted_label == "positive"
        assert result.scores["positive"] == .55 and result.decision_source == "staff"
        assert result.analysis_generation == 3 and result.lease_token is None
        assert db.get(Review, 1).updated_at == original
        assert db.scalar(select(func.count()).select_from(SentimentDecision)) == 1
        assert db.scalar(select(func.count()).select_from(OutboxRecord)) == 1
        stats = summaries(db, [3], Settings(database_url="sqlite://"))[3]
        assert stats["negative"] == 1 and stats["needs_review"] == 0


def test_stale_decision_and_reused_request_are_rejected(store):
    with Session(store) as db:
        first = command(db)
        stale = command(db)
        decide_sentiment(db, 1, 9, first)
        with pytest.raises(HTTPException) as error:
            decide_sentiment(db, 1, 10, stale)
        assert error.value.status_code == 409
        with pytest.raises(HTTPException):
            decide_sentiment(db, 1, 9, first.model_copy(update={"label": "neutral"}))


def test_edit_invalidates_effective_label_but_retains_audit(store):
    with Session(store) as db:
        decide_sentiment(db, 1, 9, command(db))
        review = db.get(Review, 1)
        review.content_version += 1
        invalidate(db, review)
        db.commit()
        result = db.get(ReviewSentiment, 1)
        assert result.label is None and result.confirmed_by_user_id is None
        assert result.predicted_label is None and result.decision_source is None
        assert db.scalar(select(func.count()).select_from(SentimentDecision)) == 1
        assert summaries(db, [3], Settings(database_url="sqlite://"))[3]["total"] == 0
