from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlmodel import select

from test_normalized_schema import pg, catalog, provider, provider_params
from app.models import Booking, BookingDetail, BookingFoodItem, ComboItem, FoodItem, SeatStatus
from app.repositories.booking_repo import BookingRepository
from app.repositories.payment_repo import PaymentRepository
from app.schemas.booking import BookingCreateRequest
from app.schemas.food import FoodSelection
from app.services.booking_service import BookingService
from app.services.food_service import FoodService
from app.services.payment_service import PaymentService


def test_catalog_and_booking_http_contract(pg, catalog):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.database import get_session
    from app.router.booking import router as booking_router
    from app.router.food import router as food_router
    from app.utils.dependencies import get_current_user
    app = FastAPI()
    app.include_router(food_router)
    app.include_router(booking_router)
    app.dependency_overrides[get_session] = lambda: pg
    app.dependency_overrides[get_current_user] = lambda: catalog["user"]
    with TestClient(app) as client:
        menu = client.get("/food-items")
        assert menu.status_code == 200 and len(menu.json()) == 7
        combo = next(item for item in menu.json() if item["id"] == 6)
        assert Decimal(combo["price"]) == Decimal("110000")
        assert combo["components"][1]["quantity"] == 2
        created = client.post("/bookings", json=request(catalog).model_dump(mode="json"))
        assert created.status_code == 201
        booking_id = created.json()["bookingId"]
        assert created.json()["totalAmount"] == 185000
        detail = client.get(f"/bookings/{booking_id}")
        assert detail.status_code == 200
        assert detail.json()["foodItems"] == created.json()["foodItems"]
        history = client.get("/bookings")
        assert next(b for b in history.json() if b["bookingId"] == booking_id)["foodItems"] == detail.json()["foodItems"]


def request(catalog, total=185000, foods=None):
    return BookingCreateRequest(userId=catalog["user"].id, showtimeId=catalog["show"].id,
        totalAmount=total, paymentMethod="Online",
        seats=[dict(seat_id=catalog["seat"].id, price=1)],
        foodItems=foods if foods is not None else [dict(food_item_id=6, quantity=1)])


def test_combo_catalog_contents_and_price(pg):
    menu = {item.id: item for item in FoodService.get_catalog(pg)}
    assert menu[6].price == Decimal("110000")
    assert [(p.name, p.quantity) for p in menu[6].components] == [
        ("Bỏng ngọt lớn", 1), ("Nước ngọt lớn", 2)]
    pg.get(FoodItem, 3).is_active = False
    pg.flush()
    assert {item.id for item in FoodService.get_catalog(pg)} == {1, 2, 4}


def test_booking_food_snapshot_and_combined_payment(pg, catalog, provider):
    created = BookingService.create_booking(pg, request(catalog), catalog["user"].id)
    assert created.totalAmount == 185000
    assert created.seats[0]["price"] == Decimal("75000")
    assert created.foodItems[0].line_total == Decimal("110000")
    assert pg.get(SeatStatus, pg.exec(select(SeatStatus.id).where(
        SeatStatus.seat_id == catalog["seat"].id)).one()).status == "HOLD"
    combo = pg.get(FoodItem, 6)
    combo.name = "Tên đã thay đổi"
    combo.price = Decimal("150000")
    pg.get(FoodItem, 3).name = "Nước mới"
    pg.exec(select(ComboItem).where(ComboItem.combo_id == 6, ComboItem.food_item_id == 3)).one().quantity = 3
    pg.flush()
    detail = BookingRepository.get_booking_with_details(pg, created.bookingId)
    assert detail["foodItems"][0]["name"] == "Combo hai người"
    assert detail["foodItems"][0]["unit_price"] == Decimal("110000")
    assert detail["foodItems"][0]["components"][1] == dict(food_item_id=3, name="Nước ngọt lớn", quantity=2)
    history = BookingRepository.get_user_bookings_with_details(pg, catalog["user"].id)
    assert next(b for b in history if b["id"] == created.bookingId)["foodItems"] == detail["foodItems"]
    attempt = PaymentRepository.create_attempt(pg, pg.get(Booking, created.bookingId))
    assert attempt.amount == Decimal("185000")
    assert PaymentService.confirm_vnpay_payment(pg, created.bookingId, "00", provider_params(attempt))["status"] == "success"
    assert len(FoodService.for_bookings(pg, [created.bookingId])[created.bookingId]) == 1


def test_optional_food_keeps_existing_booking_contract(pg, catalog):
    created = BookingService.create_booking(pg, request(catalog, 75000, []), catalog["user"].id)
    assert created.totalAmount == 75000 and created.foodItems == []


@pytest.mark.parametrize("foods,total,code", [
    ([dict(food_item_id=6, quantity=1)], 75000, 400),
    ([dict(food_item_id=99999, quantity=1)], 75000, 409),
    ([dict(food_item_id=6, quantity=1), dict(food_item_id=6, quantity=1)], 295000, 400),
])
def test_invalid_selection_or_tampered_total_creates_no_partial_order(pg, catalog, foods, total, code):
    pg.commit()  # Preserve fixture data across the service's rollback/savepoint.
    before = pg.exec(select(Booking.id)).all()
    with pytest.raises(HTTPException) as error:
        BookingService.create_booking(pg, request(catalog, total, foods), catalog["user"].id)
    assert error.value.status_code == code
    assert pg.exec(select(Booking.id)).all() == before
    assert pg.exec(select(BookingFoodItem)).all() == []


def test_food_save_failure_rolls_back_booking_and_seats(pg, catalog, monkeypatch):
    pg.commit()
    before = pg.exec(select(Booking.id)).all()
    before_details = pg.exec(select(BookingDetail.id)).all()
    def fail(*args):
        raise RuntimeError("Simulated food insert failure")
    monkeypatch.setattr(FoodService, "save", fail)
    with pytest.raises(HTTPException) as error:
        BookingService.create_booking(pg, request(catalog), catalog["user"].id)
    assert error.value.status_code == 500
    assert pg.exec(select(Booking.id)).all() == before
    assert pg.exec(select(BookingDetail.id)).all() == before_details


@pytest.mark.parametrize("quantity", [0, -1, 21, 1.5, True, "2"])
def test_invalid_quantities_rejected(quantity):
    with pytest.raises(ValidationError):
        FoodSelection(food_item_id=1, quantity=quantity)


def test_expired_hold_cannot_buy_food(pg, catalog):
    from datetime import datetime, timedelta, timezone
    hold = pg.exec(select(SeatStatus).where(SeatStatus.seat_id == catalog["seat"].id)).one()
    hold.hold_expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    pg.flush()
    with pytest.raises(HTTPException) as error:
        BookingService.create_booking(pg, request(catalog), catalog["user"].id)
    assert error.value.status_code == 400
    assert pg.exec(select(BookingFoodItem)).all() == []
