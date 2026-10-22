"""Real row-lock races. Requires an isolated PostgreSQL database, never production."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlmodel import SQLModel, Session, create_engine, select

import test_ai_features  # initialize the same test settings used by the rest of the suite
from app.models import CinemaRoom, Film, Format, Seat, SeatType, Showtime, Theater
from app.schemas.admin import SeatWrite, ShowtimeWrite
from app.services import admin_service


@pytest.fixture
def isolated_postgres():
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL is required to test PostgreSQL row locks")
    root = create_engine(url)
    if "test" not in (root.url.database or "").lower():
        pytest.fail("Use a dedicated database containing 'test' in its name")
    schema = "admin_race_" + uuid4().hex
    with root.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        SQLModel.metadata.create_all(engine)
        with Session(engine) as db:
            fmt = Format(id=1, code="2D", name="2D")
            db.add(fmt)
            db.add(Theater(id=1, name="Test", city="Test", address="Test"))
            db.flush()
            db.add(CinemaRoom(id=1, theater_id=1, name="Test", capacity=1))
            db.add_all([Film(id=i, title=f"Film {i}", duration_minutes=120, format_items=[fmt]) for i in (1, 2)])
            db.flush()
            db.add(SeatType(id=1, room_id=1, name="Standard", base_price=75000))
            db.commit()
        yield engine
    finally:
        engine.dispose()
        with root.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()


@pytest.mark.parametrize("scenario", ["showtime", "seat"])
def test_concurrent_writers_cannot_overlap_or_exceed_room_capacity(isolated_postgres, scenario):
    barrier = Barrier(2)

    def writer(index):
        with Session(isolated_postgres) as db:
            barrier.wait(timeout=10)
            try:
                if scenario == "showtime":
                    admin_service.showtime_write(db, ShowtimeWrite(film_id=index, room_id=1,
                        format_id=1, show_date=date.today()+timedelta(days=3),
                        start_time="18:00", end_time="20:00"))
                else:
                    admin_service.seat_write(db, 1, SeatWrite(seat_type_id=1, seat_name=f"A{index}"))
                return 201
            except HTTPException as error:
                db.rollback()
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(writer, (1, 2)))
    assert sorted(results) == [201, 409]
    with Session(isolated_postgres) as db:
        assert len(db.exec(select(Showtime if scenario == "showtime" else Seat)).all()) == 1
