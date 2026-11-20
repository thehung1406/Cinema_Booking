"""Historical decisions survive edits although staff label writes were removed."""
from sqlalchemy import create_engine, select, func
from sqlmodel import Session

from cinema_platform.events import MessagingBase
from review_service.models import Base, Review, ReviewSentiment, SentimentDecision
from review_service.service import invalidate


def test_edit_invalidates_effective_label_but_retains_historical_audit():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    MessagingBase.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            review = Review(id=1, user_id=2, film_id=3, content='Nội dung mẫu kiểm thử',
                            content_version=1, moderation_status='approved')
            db.add(review)
            db.add(ReviewSentiment(review_id=1, content_version=1, status='succeeded',
                                   label='negative', decision_source='staff'))
            db.add(SentimentDecision(review_id=1, actor_user_id=5, request_id='historical',
                                    content_version=1, analysis_generation=1, label='negative',
                                    reason='Historical decision', request_digest='historical'))
            db.commit()
            review.content_version += 1
            invalidate(db, review)
            db.commit()
            result = db.get(ReviewSentiment, 1)
            assert result.status == 'pending' and result.label is None
            assert result.predicted_label is None and result.decision_source is None
            assert db.scalar(select(func.count()).select_from(SentimentDecision)) == 1
    finally:
        engine.dispose()
