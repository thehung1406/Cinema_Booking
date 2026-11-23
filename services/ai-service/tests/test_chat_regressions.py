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


def test_planner_midnight_does_not_override_evening_start_after(monkeypatch):
    from datetime import time
    from ai_service.schemas import PlannerContext

    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    settings = Settings(database_url='sqlite://', redis_url='redis://localhost/0', llm_provider='openai',
                        openai_api_key='sk-test')
    monkeypatch.setattr(
        llm,
        'plan',
        lambda *args: AssistantPlan(
            intent='recommend',
            context=PlannerContext(genre='Hài', party_size=2, budget_amount=200000, budget_scope='total',
                                   start_after=time(0, 0)),
        ),
    )
    with Session(engine) as db:
        result = chat.chat(
            db,
            1,
            ChatRequest(message='Tối mai tôi muốn xem phim hài, hai người, tổng dưới 200k'),
            FakeCache(),
            Reader(),
            settings,
        )
    assert result['context']['start_after'] == '18:00:00'
    engine.dispose()


@pytest.mark.parametrize('message', ['Mã suất 1 giá vé bao nhiêu?', 'Giá vé mã suất 1, suất đầu tiên?'])
def test_explicit_showtime_clears_stale_carried_context(message):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    settings = Settings(database_url='sqlite://', redis_url='redis://localhost/0', llm_provider='disabled')
    cache, reader = FakeCache(), Reader()
    with Session(engine) as db:
        first = chat.chat(
            db,
            1,
            ChatRequest(message='Nội dung Phim không có suất'),
            cache,
            reader,
            settings,
        )
        assert first['context']['film_id'] == 2
        second = chat.chat(
            db,
            1,
            ChatRequest(
                message=message,
                conversation_id=first['conversation_id'],
                context=ToolContext(**first['context']),
            ),
            cache,
            reader,
            settings,
        )
    assert second['status'] == 'ok'
    assert second['tool'] == 'get_ticket_prices'
    assert second['context']['showtime_id'] == 1
    assert second['context']['film_id'] is None
    engine.dispose()


@pytest.mark.parametrize('followup', ['Suất đầu tiên giá vé bao nhiêu?', 'Suất thứ nhất giá vé bao nhiêu?'])
def test_first_ordinal_followup_selects_first_showtime(followup):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    settings = Settings(database_url='sqlite://', redis_url='redis://localhost/0', llm_provider='disabled')
    cache, reader = FakeCache(), Reader()
    original_run = reader.run

    def run_with_showtimes(call, evening=False):
        if call.name == 'get_showtimes':
            return [dict(id='showtime:1', title='Suất 1', text='Suất 1', url='/seat-selection/1', kind='live')]
        return original_run(call, evening)

    reader.run = run_with_showtimes
    with Session(engine) as db:
        first = chat.chat(
            db,
            1,
            ChatRequest(message='Lịch chiếu?', context=ToolContext(film_id=1, theater_id=1, show_date=Reader.day)),
            cache,
            reader,
            settings,
        )
        second = chat.chat(
            db,
            1,
            ChatRequest(message=followup, conversation_id=first['conversation_id']),
            cache,
            reader,
            settings,
        )
    assert second['status'] == 'ok'
    assert second['tool'] == 'get_ticket_prices'
    assert second['context']['showtime_id'] == 1
    engine.dispose()


def test_out_of_scope_actions_take_precedence_over_personal_order():
    assert chat.detect_intent('Thanh toán hộ đơn hàng của tôi') == 'out_of_scope'
    assert chat.detect_intent('Đặt hộ tôi vé của tôi') == 'out_of_scope'
    assert chat.detect_intent('Kiểm tra đơn hàng của tôi') == 'get_my_booking'


def test_infer_preferences_supports_spaced_hour_and_extra_genres():
    from datetime import time

    ctx = chat.infer_preferences('Tôi muốn xem phim viễn tưởng sau 19 giờ', ToolContext())
    assert ctx.genre == 'Viễn tưởng'
    assert ctx.start_after == time(19, 0)
