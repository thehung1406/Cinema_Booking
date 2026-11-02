from alembic import op
from cinema_platform.reporting_v1 import install

revision = "review_002"
down_revision = "review_001"
branch_labels = None
depends_on = None


def upgrade():
    install(
        op,
        "review",
        "SELECT 'review'::text kind,r.id::text key,jsonb_build_object('id',r.id,'film_id',r.film_id,'updated_at',r.updated_at,'content_version',r.content_version,'is_deleted',r.is_deleted,'moderation_status',r.moderation_status,'sentiment_version',s.content_version,'sentiment_status',s.status,'label',s.label,'model_version',s.model_version) payload FROM reviews r LEFT JOIN review_sentiments s ON s.review_id=r.id",
        {
            "reviews": "PERFORM report_touch('review',COALESCE(NEW.id,OLD.id)::text);",
            "review_sentiments": "PERFORM report_touch('review',COALESCE(NEW.review_id,OLD.review_id)::text);",
        },
    )


def downgrade():
    raise RuntimeError("Retain report generations and tombstones; repair forward")
