from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session

from ai_service import chat, llm
from ai_service.config import Settings
from ai_service.models import Base, utcnow
from ai_service.rag import retrieve, upsert_document
from ai_service.schemas import AssistantPlan, ChatRequest, ToolContext
from ai_support import FakeCache
from test_chat_context import Reader


def test_single_keyword_retrieval_still_respects_approval_scope_and_missing_terms():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        data = dict(source_id='book', title='Cinematography', version='1',
                    source_url='/book', effective_at=utcnow()-timedelta(days=1),
                    provenance={'scope': 'film_education'},
                    content='Cinematography is the art of motion picture photography.')
        upsert_document(db, data | {'approved': True})
        assert len(retrieve(db, 'Cinematography là gì?', scope='film_education')) == 1
        assert retrieve(db, 'Cinematography là gì?', scope='policy') == []
        assert retrieve(db, 'Unrelatedxyz là gì?', scope='film_education') == []
        assert retrieve(db, 'là gì?', scope='film_education') == []
        upsert_document(db, data | {'approved': False})
        assert retrieve(db, 'Cinematography là gì?', scope='film_education') == []
    engine.dispose()


@pytest.mark.parametrize('pending,context,reply,expected', [
    ('Lịch chiếu?', {'theater_id': 1, 'show_date': Reader.day}, 'Phim thử nghiệm', 'get_showtimes'),
    ('Lịch chiếu?', {'film_id': 1, 'show_date': Reader.day}, 'Rạp cũ', 'get_showtimes'),
    ('Giá vé?', {}, 'Mã suất 1', 'get_ticket_prices'),
    ('Lịch chiếu?', {}, 'Nội dung Phim thử nghiệm', 'search_films'),
    ('Lịch chiếu?', {}, 'Cách đặt vé?', None),
])
def test_pending_lookup_with_planner(pending, context, reply, expected, monkeypatch):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    settings = Settings(database_url='sqlite://', redis_url='redis://localhost/0', llm_provider='ollama')
    cache, reader = FakeCache(), Reader()
    monkeypatch.setattr(llm, 'plan', lambda *args: AssistantPlan(intent=chat.detect_intent(pending)))
    with Session(engine) as db:
        first = chat.chat(db, 1, ChatRequest(message=pending, context=ToolContext(**context)), cache, reader, settings)
        monkeypatch.setattr(llm, 'plan', lambda *args: AssistantPlan(intent='search_films'))
        second = chat.chat(db, 1, ChatRequest(message=reply, conversation_id=first['conversation_id']), cache, reader, settings)
        assert second['tool'] == expected
    engine.dispose()


@pytest.mark.parametrize('message,expected', [
    ('Giá vé mã suất 1?', 'get_ticket_prices'),
    ('Mã suất 1 còn ghế nào?', 'get_seat_availability'),
])
def test_explicit_lookup_does_not_call_planner(message, expected, monkeypatch):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    settings = Settings(database_url='sqlite://', redis_url='redis://localhost/0', llm_provider='ollama')
    calls = []
    def planner(*args):
        calls.append(args)
        return AssistantPlan(intent='search_films')
    monkeypatch.setattr(llm, 'plan', planner)
    with Session(engine) as db:
        result = chat.chat(db, 1, ChatRequest(message=message), FakeCache(), Reader(), settings)
    assert result['tool'] == expected and result['status'] == 'ok'
    assert calls == []
    engine.dispose()
