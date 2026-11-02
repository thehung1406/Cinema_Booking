"""Conversation regressions moved from the retired application to the AI owner."""

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlmodel import Session

from ai_service.chat import chat
from ai_service.models import AIConversation, AIMessage
from ai_service.schemas import ChatRequest, ToolContext
from ai_support import FakeCache


class Reader:
    """Only the documented read-only owner interface; no foreign ORM/database."""

    day = date.today() + timedelta(days=7)
    films = {1: "Phim thử nghiệm", 2: "Phim không có suất"}
    theaters = {1: "Rạp cũ", 2: "Rạp mới"}

    def matches(self, message):
        from ai_service.rag import folded

        value = folded(message)
        return SimpleNamespace(
            **{
                field: [
                    SimpleNamespace(id=id)
                    for id, name in rows.items()
                    if folded(name) in value
                ]
                for field, rows in [
                    ("film_id", self.films),
                    ("theater_id", self.theaters),
                ]
            }
        )

    def names(self, context):
        if context.showtime_id is not None:
            if context.showtime_id not in (1, 2) or (
                context.film_id is not None and context.film_id != context.showtime_id
            ):
                raise HTTPException(422, "Invalid showtime/film context")
        return SimpleNamespace(
            film_name=self.films.get(context.film_id),
            theater_name=self.theaters.get(context.theater_id),
        )

    def run(self, call, evening=False):
        if call.name == "get_showtimes" and (
            call.context.film_id != 1
            or call.context.theater_id != 1
            or call.context.show_date != self.day
        ):
            return []
        return [
            dict(
                id="price:1",
                title="Standard",
                text="Suất 1: 75,000 VND.",
                url="/seat-selection/1",
                kind="live",
            )
        ]


@pytest.fixture
def conversation(ai_store, ai_settings):
    cache = FakeCache()
    reader = Reader()
    with Session(ai_store) as db:

        def run(message, *, previous=None, context=None):
            return chat(
                db,
                1,
                ChatRequest(
                    message=message,
                    conversation_id=previous,
                    context=ToolContext(**(context or {})),
                ),
                cache,
                reader,
                ai_settings,
            )

        yield run, db, cache, reader


def test_policy_question_overrides_pending_lookup(conversation):
    run, *_ = conversation
    first = run("Lịch chiếu?")
    result = run("Cách đặt vé?", previous=first["conversation_id"])
    assert result["tool"] is None and result["status"] == "no_evidence"


def test_film_name_completes_pending_showtime_lookup(conversation):
    run, _, _, reader = conversation
    first = run("Lịch chiếu?", context=dict(theater_id=1, show_date=reader.day))
    assert first["missing_fields"] == ["film_id"]
    result = run("Phim thử nghiệm", previous=first["conversation_id"])
    assert result["tool"] == "get_showtimes" and result["status"] == "ok"


@pytest.mark.parametrize("message", ["Suất chiếu số 1", "Mã suất 1"])
def test_showtime_completes_pending_price_lookup(conversation, message):
    run, *_ = conversation
    first = run("Giá vé bao nhiêu?")
    assert first["missing_fields"] == ["showtime_id"]
    result = run(message, previous=first["conversation_id"])
    assert result["status"] == "ok" and "75,000" in result["answer"]


@pytest.mark.parametrize(
    "message,tool",
    [
        ("Nội dung Phim thử nghiệm", "search_films"),
        ("Giá vé mã suất 1", "get_ticket_prices"),
        ("Cách đặt vé Phim thử nghiệm", None),
        ("Đặt hộ Phim thử nghiệm", None),
    ],
)
def test_explicit_new_request_overrides_pending_lookup(conversation, message, tool):
    run, *_ = conversation
    first = run("Lịch chiếu?")
    assert run(message, previous=first["conversation_id"])["tool"] == tool


@pytest.mark.parametrize("field", ["film_id", "theater_id", "show_date"])
@pytest.mark.parametrize("via_message", [True, False])
def test_selection_change_clears_carried_showtime(conversation, field, via_message):
    run, db, _, reader = conversation
    first = run(
        "Giá vé?",
        context=dict(film_id=1, theater_id=1, show_date=reader.day, showtime_id=1),
    )
    values = dict(
        film_id=(2, "Nội dung Phim không có suất"),
        theater_id=(2, "Lịch chiếu Rạp mới"),
        show_date=(
            (reader.day + timedelta(days=1)).isoformat(),
            f"Lịch chiếu {reader.day + timedelta(days=1):%Y-%m-%d}",
        ),
    )
    value, message = values[field]
    submitted = first["context"].copy()
    if not via_message:
        submitted[field] = value
        message = "Nội dung phim" if field == "film_id" else "Lịch chiếu?"
    result = run(message, previous=first["conversation_id"], context=submitted)
    assert result["context"][field] == value
    assert result["context"]["showtime_id"] is None
    assert result["status"] == ("ok" if field == "film_id" else "no_results")
    assert (
        db.get(AIConversation, UUID(first["conversation_id"])).context["context"][
            "showtime_id"
        ]
        is None
    )


def test_unchanged_selection_preserves_showtime(conversation):
    run, _, _, reader = conversation
    first = run(
        "Giá vé?",
        context=dict(film_id=1, theater_id=1, show_date=reader.day, showtime_id=1),
    )
    result = run(
        "Giá vé Phim thử nghiệm?",
        previous=first["conversation_id"],
        context=first["context"],
    )
    assert result["context"]["showtime_id"] == 1 and result["status"] == "ok"


@pytest.mark.parametrize("via_message", [True, False])
@pytest.mark.parametrize("matching", [True, False])
def test_new_explicit_showtime_is_validated(conversation, via_message, matching):
    run, *_ = conversation
    first = run("Giá vé?", context=dict(film_id=1, showtime_id=1))
    showtime = 2 if matching or not via_message else 1
    film = 2 if matching or via_message else 1
    message = (
        f"Giá vé Phim không có suất, mã suất {showtime}" if via_message else "Giá vé?"
    )
    context = (
        first["context"] if via_message else dict(film_id=film, showtime_id=showtime)
    )
    if matching:
        assert (
            run(message, previous=first["conversation_id"], context=context)["context"][
                "showtime_id"
            ]
            == 2
        )
    else:
        with pytest.raises(HTTPException) as error:
            run(message, previous=first["conversation_id"], context=context)
        assert error.value.status_code == 422


def test_invalid_context_creates_no_partial_history(conversation):
    run, db, *_ = conversation
    with pytest.raises(HTTPException):
        run("Giá vé?", context=dict(showtime_id=999))
    assert db.scalar(select(func.count()).select_from(AIConversation)) == 0
    assert db.scalar(select(func.count()).select_from(AIMessage)) == 0


def test_cache_write_failure_does_not_lose_persisted_reply(conversation):
    run, db, cache, _ = conversation
    cache.setex = lambda *args: (_ for _ in ()).throw(ConnectionError())
    result = run("Giá vé?", context=dict(showtime_id=1))
    assert result["status"] == "ok"
    assert db.get(AIConversation, UUID(result["conversation_id"])) is not None
    assert db.scalar(select(func.count()).select_from(AIMessage)) == 2
