from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from zoneinfo import ZoneInfo
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from catalog_service import service
from catalog_service.models import Film, Format, ScheduleBinding, FoodQuote, FoodItem, utcnow
from catalog_service.schemas import BindingRequest
from catalog_support import HEADERS, film_body, binding_body


def private(settings):
    return {"X-Service-Key": settings.service_key}


def test_public_films_menu_search_and_authorization(catalog_client, catalog_settings):
    client = catalog_client
    films = client.get("/films/").json()
    assert films[0]["title"] == "Catalog Film" and films[0]["genre"] == "Drama"
    assert "catalog_version" not in films[0]
    assert client.get("/films/1").json()["formats"] == ["2D"]
    assert client.get("/films/999").status_code == 404
    assert len(client.get("/food-items").json()) == 3
    assert client.get("/admin/catalog").status_code == 401
    assert client.get("/admin/catalog", headers=HEADERS).json()["formats"][0]["code"] == "2D"
    client.auth_state["permissions"] = ["rooms.manage"]
    assert client.get("/admin/catalog", headers=HEADERS).status_code == 200
    assert client.post("/admin/films", headers=HEADERS, json=film_body()).status_code == 403
    assert client.post("/internal/v1/films/batch", json={"ids": [1]}).status_code == 401
    facts = client.post("/internal/v1/films/batch", headers=private(catalog_settings), json={"ids": [1]}).json()
    assert facts[0]["catalog_version"] == 1


def test_upcoming_search_only_returns_future_releases_in_date_order(catalog_client, catalog_settings):
    today = utcnow().astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    for days, title in [(8, "Later release"), (3, "Next release"), (-40, "Past release")]:
        response = catalog_client.post("/admin/films", headers=HEADERS, json=film_body(
            title=title, release_date=(today + timedelta(days=days)).isoformat(),
            end_date=(today + timedelta(days=days + 30)).isoformat(),
        ))
        assert response.status_code == 201
    result = catalog_client.post("/internal/v1/films/search", headers=private(catalog_settings),
                                 json={"upcoming": True, "genre": "Drama", "limit": 2})
    assert [film["title"] for film in result.json()] == ["Next release", "Later release"]


def test_film_create_edit_soft_retire_preserves_id_and_no_auth_role_escalation(catalog_client, catalog_store):
    client = catalog_client
    created = client.post("/admin/films", headers=HEADERS, json=film_body(title="New film"))
    assert created.status_code == 201
    film_id = created.json()["id"]
    assert film_id > 1000000
    assert client.put(f"/admin/films/{film_id}", headers=HEADERS, json=film_body(title="Updated")).json()["catalog_version"] == 2
    assert client.delete(f"/admin/films/{film_id}", headers=HEADERS).status_code == 200
    assert client.get(f"/films/{film_id}").status_code == 404
    with Session(catalog_store) as db:
        assert db.get(Film, film_id).deleted_at is not None
    client.auth_state["permissions"] = []
    assert client.get("/admin/films", headers=HEADERS).status_code == 403


def test_binding_idempotency_snapshot_and_metadata_lifecycle(catalog_client, catalog_store, catalog_settings):
    client = catalog_client
    body = binding_body()
    headers = private(catalog_settings)
    result = client.post("/internal/v1/schedule-bindings", headers=headers, json=body)
    assert result.status_code == 200
    assert result.json()["film_snapshot"]["format_name"] == "2D"
    assert client.delete('/admin/films/1', headers=HEADERS).status_code == 409
    assert client.put('/admin/films/1', headers=HEADERS, json=film_body(duration_minutes=121)).status_code == 409
    assert client.put('/admin/films/1', headers=HEADERS, json=film_body(end_date=film_body()["release_date"])).status_code == 409
    assert client.put('/admin/films/1', headers=HEADERS, json=film_body(title="Renamed")).status_code == 200
    replay = client.post("/internal/v1/schedule-bindings", headers=headers, json=body)
    assert replay.json() == result.json()  # Previously granted immutable revision remains valid.
    assert client.post("/internal/v1/schedule-bindings", headers=headers, json={**body, "start_time": "17:00"}).status_code == 409
    with Session(catalog_store) as db:
        db.add(Format(id=2, code="3D", name="3D"))
        db.commit()
    assert client.put('/admin/films/1', headers=HEADERS, json=film_body(format_ids=[2])).status_code == 409


@pytest.mark.parametrize("changes,status", [({"format_id": 999}, 400), ({"end_time": "19:00"}, 400),
    ({"show_date": "2020-01-01"}, 400), ({"end_time": "17:00"}, 422)])
def test_binding_validates_format_date_duration(catalog_client, catalog_settings, changes, status):
    response = catalog_client.post('/internal/v1/schedule-bindings', headers=private(catalog_settings), json=binding_body(**changes))
    assert response.status_code == status


def test_concurrent_bind_and_retire_cannot_both_succeed(catalog_client, catalog_store):
    barrier = Barrier(2)
    body = BindingRequest.model_validate(binding_body())
    def action(kind):
        with Session(catalog_store) as db:
            barrier.wait(timeout=10)
            try:
                if kind == "bind": service.bind_schedule(db, body)
                else: service.retire_film(db, 1)
                return 200
            except HTTPException as exc:
                db.rollback()
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(action, ["bind", "retire"]))
    assert sorted(result) in [[200, 404], [200, 409]]
    with Session(catalog_store) as db:
        film = db.get(Film, 1)
        count = db.scalar(select(func.count()).select_from(ScheduleBinding))
        assert not (film.deleted_at is not None and count)


def test_quote_preserves_price_components_and_versions_after_menu_edit(catalog_client, catalog_store, catalog_settings):
    client = catalog_client
    headers = private(catalog_settings)
    body = {"selections": [{"food_item_id": 3, "quantity": 2}]}
    first = client.post('/internal/v1/food-quotes', headers=headers, json=body).json()
    assert Decimal(first["total"]) == Decimal("50000")
    assert first["lines"][0]["components"][1]["quantity"] == 2
    changed = client.put('/admin/food-items/3', headers=HEADERS, json=dict(name="Changed combo", category="COMBO", price="29999.99",
        components=[{"food_item_id": 1, "quantity": 2}]))
    assert changed.status_code == 200
    old = client.get('/internal/v1/food-quotes/'+first["id"], headers=headers).json()
    assert old == first
    second = client.post('/internal/v1/food-quotes', headers=headers, json=body).json()
    assert Decimal(second["total"]) == Decimal("59999.98")
    assert second["lines"][0]["catalog_version"] == 2 and second["lines"][0]["components"][0]["quantity"] == 2
    assert len(second["lines"][0]["components"]) == 1


def test_quote_validation_server_price_and_component_availability(catalog_client, catalog_settings):
    client = catalog_client
    headers = private(catalog_settings)
    # Any submitted price is ignored; only ID and quantity are business input.
    result = client.post('/internal/v1/food-quotes', headers=headers, json={"selections": [{"food_item_id": 1, "quantity": 2, "unit_price": "0.01"}]}).json()
    assert Decimal(result["total"]) == Decimal("40000")
    duplicate = {"selections": [{"food_item_id": 1, "quantity": 1}]*2}
    assert client.post('/internal/v1/food-quotes', headers=headers, json=duplicate).status_code == 400
    for quantity in [0, 21, 1.5, "2"]:
        assert client.post('/internal/v1/food-quotes', headers=headers, json={"selections": [{"food_item_id": 1, "quantity": quantity}]}).status_code == 422
    assert client.put('/admin/food-items/1', headers=HEADERS, json=dict(name="Popcorn", category="POPCORN", price="20000", is_active=False)).status_code == 200
    assert client.post('/internal/v1/food-quotes', headers=headers, json={"selections": [{"food_item_id": 3, "quantity": 1}]}).status_code == 409
    assert [row["id"] for row in client.get('/food-items').json()] == [2]


def test_expiry_and_maintenance_block_new_quotes_and_bindings(catalog_client, catalog_store, catalog_settings):
    client = catalog_client
    headers = private(catalog_settings)
    result = client.post('/internal/v1/food-quotes', headers=headers, json={"selections": [{"food_item_id": 1, "quantity": 1}]}).json()
    with Session(catalog_store) as db:
        db.get(FoodQuote, result["id"]).expires_at = utcnow()-timedelta(seconds=1)
        db.commit()
    assert client.get('/internal/v1/food-quotes/'+result["id"], headers=headers).status_code == 409
    catalog_settings.writes_enabled = False
    assert client.post('/internal/v1/food-quotes', headers=headers, json={"selections": []}).status_code == 503
    assert client.post('/internal/v1/schedule-bindings', headers=headers, json=binding_body()).status_code == 503
    assert client.get('/films/').status_code == 200
