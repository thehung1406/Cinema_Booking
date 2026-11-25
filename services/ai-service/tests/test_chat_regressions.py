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


@pytest.mark.parametrize('message,expected', [
    ('Có phim gì hay không?', 'get_showing_films'),
    ('Danh sách phim', 'get_showing_films'),
    ('Tôi muốn xem lịch chiếu phim Dune', 'get_showtimes'),
    ('Tôi muốn xem giá vé mã suất 1', 'get_ticket_prices'),
    ('Tôi muốn xem ghế trống mã suất 1', 'get_seat_availability'),
    ('Ngày mai muốn xem phim hài', 'recommend'),
    ('Mấy giờ rạp mở cửa?', 'knowledge'),
    ('Rạp đóng cửa mấy giờ?', 'knowledge'),
    ('Phim này chiếu mấy giờ?', 'get_showtimes'),
])
def test_detect_intent_regressions(message, expected):
    assert chat.detect_intent(message) == expected


def test_knowledge_retrieval_fallback_failure_returns_tool_unavailable(monkeypatch):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    settings = Settings(database_url='sqlite://', redis_url='redis://localhost/0', writes_enabled=True)
    cache = FakeCache()

    def broken(*args, **kwargs):
        raise RuntimeError('Retrieval down')

    monkeypatch.setattr(chat, 'retrieve_knowledge', broken)
    with Session(engine) as db:
        result = chat.chat(db, 1, ChatRequest(message='Mấy giờ rạp mở cửa?'), cache, Reader(), settings)
    assert result['status'] == 'tool_unavailable'
    assert result['mode'] == 'retrieval_unavailable'
    assert result['sources'] == []
    assert cache.values == {}
    engine.dispose()


def test_knowledge_retrieval_fallback_receives_deadline_and_recovers(monkeypatch):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    settings = Settings(database_url='sqlite://', redis_url='redis://localhost/0', writes_enabled=True)
    calls = []

    def flaky(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError('Primary strategy unavailable')
        return ([{'id': 'doc:1', 'title': 'Giờ mở cửa', 'text': 'Rạp mở cửa từ 8h sáng.', 'url': '/faq', 'kind': 'document'}], 'disabled', [])

    monkeypatch.setattr(chat, 'retrieve_knowledge', flaky)
    with Session(engine) as db:
        result = chat.chat(db, 1, ChatRequest(message='Mấy giờ rạp mở cửa?'), FakeCache(), Reader(), settings)
    assert len(calls) == 2
    assert calls[1].get('deadline') is not None
    assert result['status'] == 'ok'
    assert result['mode'] == 'retrieval_unavailable'
    assert '8h' in result['answer']
    engine.dispose()


def test_reader_deadline_is_capped_by_chat_budget_on_standard_turns():
    from time import monotonic

    class DeadlinedReader(Reader):
        def __init__(self):
            self.deadline = monotonic() + 100

    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    settings = Settings(database_url='sqlite://', redis_url='redis://localhost/0', writes_enabled=True)
    reader = DeadlinedReader()
    cache = FakeCache()
    with Session(engine) as db:
        result = chat.chat(db, 1, ChatRequest(message='Lịch chiếu?'), cache, reader, settings)
    assert result['status'] == 'needs_clarification'
    assert reader.deadline <= monotonic() + chat.CHAT_INFERENCE_BUDGET
    assert cache.values == {}
    engine.dispose()


def test_openai_llm_first_can_route_natural_showing_films_query(monkeypatch):
    class ListingReader(Reader):
        def showing_films(self, context):
            return ([{'id': 'film:7', 'title': 'Phim hay', 'text': 'Phim hay', 'url': '/movie/7', 'kind': 'film'}], False)

    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    settings = Settings(database_url='sqlite://', redis_url='redis://localhost/0',
                        writes_enabled=True, llm_provider='openai', openai_api_key='test-key')
    monkeypatch.setattr(llm, 'plan', lambda *args: AssistantPlan(intent='get_showing_films'))
    with Session(engine) as db:
        result = chat.chat(db, 1, ChatRequest(message='Dạo này ở rạp có gì xem không?', context=ToolContext(film_id=1)),
                           FakeCache(), ListingReader(), settings)
    assert result['tool'] == 'get_showing_films'
    assert result['mode'] == 'model_planned'
    assert result['status'] == 'ok'
    assert result['context']['film_id'] is None
    assert 'Phim hay' in result['answer']
    engine.dispose()


def test_openai_fast_path_skips_planner_for_explicit_policy_and_out_of_scope(monkeypatch):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    settings = Settings(database_url='sqlite://', redis_url='redis://localhost/0',
                        writes_enabled=True, llm_provider='openai', openai_api_key='test-key')
    calls = []
    monkeypatch.setattr(llm, 'plan', lambda *args: calls.append(args) or AssistantPlan(intent='search_films'))
    with Session(engine) as db:
        policy = chat.chat(db, 1, ChatRequest(message='Chính sách hoàn tiền thế nào?'), FakeCache(), Reader(), settings)
        oos = chat.chat(db, 1, ChatRequest(message='Đặt hộ tôi 2 vé tối nay'), FakeCache(), Reader(), settings)
    assert policy['tool'] is None
    assert oos['status'] == 'out_of_scope'
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
