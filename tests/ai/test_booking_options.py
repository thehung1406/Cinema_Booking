from datetime import date, timedelta, time

from sqlalchemy import create_engine
from sqlmodel import Session


def test_budget_and_availability_are_applied_before_pagination(monkeypatch):
    monkeypatch.setenv("BOOKING_DATABASE_URL", "sqlite://")
    from booking_service.models.sales import SalesBase, SalesConfiguration, SalesGate
    from booking_service.schemas.options import BookingOptions
    from booking_service import options
    engine = create_engine("sqlite://")
    SalesBase.metadata.create_all(engine)
    day = date.today()+timedelta(days=10)
    with Session(engine) as db:
        for identifier, price in ((1, "500000"), (2, "50000"), (3, "60000")):
            db.add(SalesConfiguration(showtime_id=identifier, sales_version=1, digest="a"*64,
                film_id=1, room_id=1, theater_id=1, show_date=day, start_time=time(19), end_time=time(21), status="ACTIVE",
                snapshot={"film": {"title": "Phim Hài", "genre": "Hài", "format_name": "2D", "duration_minutes": 100},
                    "theater": {"name": "Rạp mẫu", "city": "Hà Nội"}, "room": {"name": "Phòng 1"},
                    "seats": [{"id": 1, "status": "ACTIVE", "price": price}, {"id": 2, "status": "ACTIVE", "price": "900000"}]}))
            db.add(SalesGate(showtime_id=identifier, sales_version=1, epoch=1, action="OPEN", is_open=True))
        db.commit()
        monkeypatch.setattr(options, "availability", lambda db, identifier: [
            {"seat_id": 1, "status": "AVAILABLE"}, {"seat_id": 2, "status": "BOOKED"}])
        response = options.discover(db, BookingOptions(show_date=day, genre="hai", budget_per_ticket="100000", limit=1))
        assert response["items"][0]["showtime_id"] == 2
        assert response["items"][0]["min_ticket_price"] == "50000"
        assert response["has_more"] and response["next_offset"] == 1
        response = options.discover(db, BookingOptions(show_date=day, party_size=2))
        assert response["items"] == []  # Booked seats cannot make a two-ticket option feasible.
