"""Exercise additive migrations against old rows in an isolated PostgreSQL schema."""
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.mark.parametrize("domain,initial", [("ai", "ai_001"), ("review", "review_001")])
def test_new_migrations_preserve_existing_rows(monkeypatch, domain, initial):
    url = os.environ.get(f"{domain.upper()}_DATABASE_URL", "")
    if "test" not in url:
        pytest.skip("Isolated PostgreSQL required for migration validation")
    schema = "ai_feature_migration_"+uuid4().hex
    root = create_engine(url)
    with root.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = make_url(url).update_query_dict({"options": f"-csearch_path={schema},public"})
    monkeypatch.setenv(f"{domain.upper()}_DATABASE_URL", isolated.render_as_string(hide_password=False))
    config = Config(str(Path(__file__).resolve().parents[2]/f"services/{domain}-service/alembic.ini"))
    engine = create_engine(isolated)
    try:
        command.upgrade(config, initial)
        with engine.begin() as connection:
            if domain == "ai":
                connection.execute(text("INSERT INTO ai_documents(source_id,title,version,source_url,approved,effective_at,updated_at) "
                    "VALUES ('old','Original','1','/about',true,now(),now())"))
            else:
                connection.execute(text("INSERT INTO reviews(id,user_id,film_id,content,content_version,moderation_status,is_deleted,created_at,updated_at) "
                    "VALUES (1,1,1,'Original',1,'approved',false,now(),now())"))
                connection.execute(text("INSERT INTO review_sentiments(review_id,content_version,status,label,scores,model_version,attempts,updated_at) "
                    "VALUES (1,1,'succeeded','positive','{}','original-model',1,now())"))
        command.upgrade(config, "head")
        with engine.connect() as connection:
            if domain == "ai":
                row = connection.execute(text("SELECT title,provenance FROM ai_documents")).one()
                assert row.title == "Original" and row.provenance == {}
            else:
                row = connection.execute(text("SELECT label,predicted_label,decision_source,confirmed_by_user_id FROM review_sentiments")).one()
                assert row.label == row.predicted_label == "positive" and row.decision_source == "model"
                assert row.confirmed_by_user_id is None
    finally:
        engine.dispose()
        with root.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()
