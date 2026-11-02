import os
from uuid import uuid4

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, select, text
from sqlmodel import Session

from ai_service.migrate import TABLES, transfer
from ai_service.models import AIConversation, AIMessage, KnowledgeDocument, KnowledgeChunk, utcnow


def test_backfill_preserves_ids_metadata_embeddings_sequences_and_refuses_overwrite(ai_store):
    root = create_engine(os.environ["TEST_POSTGRES_URL"])
    schema = "ai_copy_test_" + uuid4().hex
    with root.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    source = create_engine(os.environ["TEST_POSTGRES_URL"], connect_args={"options": f"-csearch_path={schema}"})
    cid = uuid4()
    try:
        # Clone actual Alembic-created legacy columns/constraints, including its user FK.
        # Only the external FK's parent is minimal; it must not be copied to the AI target.
        legacy = MetaData()
        users = Table("users", legacy, Column("id", Integer, primary_key=True))
        for name in TABLES:
            Table(name, legacy, autoload_with=root, resolve_fks=False)
        legacy.create_all(source)
        with source.begin() as conn:
            conn.execute(users.insert().values(id=777))
        with Session(source) as db:
            db.add(KnowledgeDocument(id=5, source_id="test-copy", title="Giữ ghế", version="old-version", source_url="/booking", approved=True, effective_at=utcnow()))
            db.add(AIConversation(id=cid, user_id=777, title="Hội thoại cũ", context={"context": {"showtime_id": 1}}))
            db.flush()
            db.add(KnowledgeChunk(id=11, document_id=5, content="Nội dung gốc", embedding=[0.25] * 256, embedding_version="legacy-preserved"))
            db.add(AIMessage(id=1002, conversation_id=cid, role="assistant", content="Giá vé đã tra", details={"sources": [{"id": "source:old", "version": "1"}]}))
            db.commit()
        with source.begin() as conn:
            conn.execute(text("SELECT setval(pg_get_serial_sequence('ai_messages','id'), 100000, true)"))
        with pytest.raises(ValueError):
            transfer(source, ai_store, apply=True, frozen=False)
        result = transfer(source, ai_store, apply=True, frozen=True)
        assert result["verified"] and result["copied"]
        assert transfer(source, ai_store, apply=True, frozen=True)["copied"] is False
        with Session(ai_store) as db:
            assert db.get(AIConversation, cid).user_id == 777
            assert db.get(KnowledgeChunk, 11).embedding == [0.25] * 256
            assert db.get(AIMessage, 1002).details["sources"][0]["id"] == "source:old"
            new = AIMessage(conversation_id=cid, role="user", content="Tiếp tục")
            db.add(new)
            db.commit()
            assert new.id > 100000
        with pytest.raises(ValueError):
            transfer(source, ai_store, apply=True, frozen=True)
        with Session(ai_store) as db:
            assert len(db.execute(select(AIMessage)).all()) == 2
    finally:
        source.dispose()
        with root.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()
