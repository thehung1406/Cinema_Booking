import os
from uuid import uuid4
import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, text
from sqlmodel import Session
from review_service.migrate import TABLES, transfer
from review_service.models import Review, ReviewSentiment, utcnow
from review_service import service


def test_real_legacy_schema_copy_versions_deletion_scores_sequences_and_no_overwrite(review_store, review_settings):
    root = create_engine(os.environ["TEST_POSTGRES_URL"])
    schema = "review_copy_test_" + uuid4().hex
    with root.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    source = create_engine(os.environ["TEST_POSTGRES_URL"], connect_args={"options": f"-csearch_path={schema}"})
    try:
        legacy = MetaData()
        users = Table("users", legacy, Column("id", Integer, primary_key=True))
        films = Table("films", legacy, Column("id", Integer, primary_key=True))
        for name in TABLES:
            Table(name, legacy, autoload_with=root, resolve_fks=False)
        legacy.create_all(source)
        now = utcnow()
        with source.begin() as connection:
            connection.execute(users.insert().values(id=777))
            connection.execute(films.insert().values(id=888))
            connection.execute(legacy.tables["reviews"].insert().values(id=41, user_id=777, film_id=888,
                content="", content_version=8, moderation_status="rejected", is_deleted=True, created_at=now, updated_at=now))
            connection.execute(legacy.tables["review_sentiments"].insert().values(review_id=41, content_version=7,
                status="succeeded", label="positive", scores={"positive": .8, "neutral": .1, "negative": .1},
                model_version="legacy-model-7", attempts=3, updated_at=now))
            connection.execute(text("SELECT setval(pg_get_serial_sequence('reviews','id'), 100000, true)"))
        with pytest.raises(ValueError):
            transfer(source, review_store, apply=True)
        assert transfer(source, review_store, apply=True, frozen=True)["copied"]
        assert not transfer(source, review_store, apply=True, frozen=True)["copied"]
        with Session(review_store) as db:
            row, result = db.get(Review, 41), db.get(ReviewSentiment, 41)
            assert row.is_deleted and row.content_version == 8 and row.event_version == 0
            assert result.content_version == 7 and result.model_version == "legacy-model-7" and result.attempts == 3
            assert result.scores["positive"] == .8 and result.analysis_generation == 1 and result.lease_token is None
            new = service.create_review(db, 2, 999, "Tài khoản/phim ngoài store", review_settings)
            assert new.id > 100000
        with pytest.raises(ValueError):
            transfer(source, review_store, apply=True, frozen=True)
    finally:
        source.dispose()
        with root.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()
