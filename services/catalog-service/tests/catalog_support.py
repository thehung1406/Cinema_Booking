import os
from datetime import date, timedelta
from uuid import uuid4
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from catalog_service.config import Settings
from catalog_service.main import create_app
from catalog_service.models import Base, Genre, Format, Film, FoodItem, ComboItem


@pytest.fixture
def catalog_store():
    url = os.environ.get("CATALOG_DATABASE_URL", "")
    if "test" not in url:
        pytest.skip("Dedicated Catalog test database required")
    root = create_engine(url)
    schema = "catalog_test_" + uuid4().hex
    with root.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with root.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()


@pytest.fixture
def catalog_settings():
    return Settings(writes_enabled=True)


@pytest.fixture
def catalog_client(catalog_store, catalog_settings):
    with Session(catalog_store) as db:
        genre = Genre(id=1, name="Drama")
        fmt = Format(id=1, code="2D", name="2D")
        db.add_all([genre, fmt])
        db.flush()
        db.add(Film(id=1, title="Catalog Film", duration_minutes=120, release_date=date.today(),
            end_date=date.today()+timedelta(days=30), genre_items=[genre], format_items=[fmt]))
        db.add_all([FoodItem(id=1, name="Popcorn", category="POPCORN", price="20000.00"),
                    FoodItem(id=2, name="Drink", category="DRINK", price="10000.00"),
                    FoodItem(id=3, name="Combo", category="COMBO", price="25000.00")])
        db.flush()
        db.add_all([ComboItem(combo_id=3, food_item_id=1, quantity=1), ComboItem(combo_id=3, food_item_id=2, quantity=2)])
        # Explicit fixture IDs must not collide with generated API IDs.
        for table in ("films", "genres", "formats", "food_items"):
            db.execute(text("SELECT setval(pg_get_serial_sequence(:name,'id'),1000000,true)"), {"name": table})
        db.commit()
    state = {"user_id": 91, "role": "ADMIN", "permissions": ["films.manage"], "is_active": True}
    def auth(request):
        return httpx.Response(200, json=state)
    app = create_app(catalog_settings, engine=catalog_store, auth_transport=httpx.MockTransport(auth))
    with TestClient(app) as client:
        client.auth_state = state
        yield client


HEADERS = {"Authorization": "Bearer catalog-test-token"}


def film_body(**changes):
    body = dict(title="Catalog Film", duration_minutes=120, release_date=date.today().isoformat(),
        end_date=(date.today()+timedelta(days=30)).isoformat(), genre_ids=[1], format_ids=[1])
    return {**body, **changes}


def binding_body(**changes):
    body = dict(id=str(uuid4()), film_id=1, format_id=1, show_date=(date.today()+timedelta(days=5)).isoformat(),
                start_time="18:00", end_time="20:00")
    return {**body, **changes}
