from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, select

from ai_service.models import Base, KnowledgeChunk
from ai_service.rag import upsert_document
from scripts.ai.evaluate_rag import measure


def test_overlap_preserves_exact_character_provenance_without_extra_tail():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    content = ''.join(chr(0x400 + i % 400) for i in range(500))
    try:
        with Session(engine) as db:
            data = dict(source_id='test-source', title='Test', version='1', source_url='/test',
                effective_at=datetime.now(timezone.utc), content=content, approved=False)
            upsert_document(db, data, chunk_size=300, chunk_overlap=100)
            chunks = db.exec(select(KnowledgeChunk).order_by(KnowledgeChunk.id)).all()
            assert len(chunks) == 2
            assert [c.provenance['character_start'] for c in chunks] == [0, 200]
            assert all(c.content == content[c.provenance['character_start']:c.provenance['character_end']] for c in chunks)
            with pytest.raises(ValueError):
                upsert_document(db, data, chunk_size=300, chunk_overlap=300)
    finally:
        engine.dispose()


def test_correct_pdf_page_without_the_target_passage_is_not_a_retrieval_hit():
    target = [dict(source_id='book', version='1', pages=[26], text_contains=['definition'], grade=2)]
    distractor = dict(source_id='book', version='1', provenance={'page_start':26}, text='Unrelated example')
    assert measure([distractor], target, 3)['recall_at_k'] == 0
    assert measure([distractor | {'text':'Actual definition here'}], target, 3)['recall_at_k'] == 1
