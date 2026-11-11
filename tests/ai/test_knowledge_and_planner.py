from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlmodel import Session

from ai_service.models import Base, utcnow
from ai_service.rag import upsert_document, retrieve
from ai_service.schemas import DocumentWrite, ToolContext
from ai_service.config import Settings
from ai_service.chat import infer_preferences
from ai_service.llm import grounded_answer


def test_pdf_provenance_scope_and_revocation():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    data = DocumentWrite(source_id="book", title="Film genre", version="1", source_url="https://example.org/book.pdf",
        effective_at=utcnow()-timedelta(days=1), provenance=dict(source_type="pdf", scope="film_education",
            license="test-only", checksum="a"*64, language="en"),
        blocks=[dict(text="Film genre groups movies by narrative and style.", page_start=7, page_end=7)])
    with Session(engine) as db:
        upsert_document(db, data.model_dump() | {"approved": True})
        assert retrieve(db, "film genre", strategy="bm25", scope="policy") == []
        rows = retrieve(db, "film genre", strategy="bm25", scope="film_education")
        assert rows[0]["url"] == "https://example.org/book.pdf#page=7"
        assert rows[0]["provenance"]["checksum"] == "a"*64
        upsert_document(db, data.model_dump() | {"approved": False})
        assert retrieve(db, "film genre", strategy="bm25", scope="film_education") == []


def test_budget_requires_explicit_scope_and_count_is_validated():
    context = infer_preferences("Muốn xem phim hài, hai người, dưới 250k", ToolContext())
    assert context.party_size == 2 and context.budget_amount == 250000
    assert context.budget_scope == "unknown"
    assert infer_preferences("tổng ngân sách dưới 250k", context).budget_scope == "total"
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        infer_preferences("muốn đặt 99 vé", ToolContext())


def test_generator_rejects_invented_citations(monkeypatch):
    settings = Settings(database_url="sqlite://", redis_url="redis://localhost/0", llm_provider="ollama")
    original = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"message": {
        "content": '{"sentences":[{"source_id":"invented","text":"Unsupported claim"}]}'}}))
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(transport=transport, **kwargs))
    with pytest.raises(ValueError, match="invented"):
        grounded_answer(settings, "What?", [{"id": "doc:1", "text": "Known evidence"}])


def test_unknown_budget_does_not_call_booking():
    from ai_service.recommendations import recommend
    reader = SimpleNamespace(call=lambda *args, **kwargs: pytest.fail("Should ask first"))
    result = recommend(reader, ToolContext(budget_amount="100000"))
    assert result["missing_fields"] == ["budget_scope"]


def test_short_film_title_does_not_capture_relative_date():
    from catalog_service.matching import title_mentioned
    assert not title_mentioned("Tối mai tôi muốn xem phim hài", "Mai")
    assert not title_mentioned("Ngày mai có suất nào?", "Mai")
    assert not title_mentioned("Showtimes", "It")
    assert title_mentioned("Tối mai tôi muốn xem phim Mai", "Mai")
    assert title_mentioned('Suất chiếu của "Mai"', "Mai")
    assert title_mentioned("Mai", "Mai")
    assert title_mentioned("Ngày mai xem Kung Fu Panda 4", "Kung Fu Panda 4")


def test_dense_scores_batches_large_scopes_without_changing_score_order(monkeypatch):
    import json
    from ai_service.rag import dense_scores

    original = httpx.Client
    batch_sizes = []

    def respond(request):
        texts = json.loads(request.content)["texts"]
        assert len(texts) <= 1000
        assert sum(map(len, texts)) <= 2_000_000
        batch_sizes.append(len(texts))
        return httpx.Response(200, json={"scores": [int(text[:4]) for text in texts]})

    monkeypatch.setattr(httpx, "Client", lambda **kwargs:
        original(transport=httpx.MockTransport(respond), **kwargs))
    documents = [f"{index:04d}" + "x" * 3996 for index in range(1001)]
    assert dense_scores("film genre", documents, "http://inference") == list(range(1001))
    assert sum(batch_sizes) == len(documents) and len(batch_sizes) > 1
