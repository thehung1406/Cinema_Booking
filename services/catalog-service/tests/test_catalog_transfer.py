import os
from datetime import date, time, timedelta
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, select, text
from sqlalchemy.orm import Session
from catalog_service.migrate import TABLES, transfer
from catalog_service.models import Film, ScheduleBinding


def test_actual_source_copy_preserves_catalog_bindings_money_and_sequences(catalog_store):
    root = create_engine(os.environ["TEST_POSTGRES_URL"])
    schema = "catalog_copy_test_" + uuid4().hex
    with root.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    source = create_engine(os.environ["TEST_POSTGRES_URL"], connect_args={"options": f"-csearch_path={schema}"})
    try:
        metadata = MetaData()
        rooms = Table("cinema_rooms", metadata, Column("id", Integer, primary_key=True))
        for name in (*TABLES, "showtimes"):
            Table(name, metadata, autoload_with=root, resolve_fks=False)
        metadata.create_all(source)
        binding_id = str(uuid4())
        fact = dict(id=41, title="Historical film", duration_minutes=120, catalog_version=1,
                    genre="Drama", formats=["2D"], format_name="2D", genre_ids=[1], format_ids=[1])
        with source.begin() as conn:
            conn.execute(rooms.insert().values(id=1))
            conn.execute(metadata.tables["genres"].insert().values(id=1, name="Drama"))
            conn.execute(metadata.tables["formats"].insert().values(id=1, code="2D", name="2D"))
            conn.execute(metadata.tables["films"].insert().values(id=41, title="Historical film", duration_minutes=120,
                release_date=date.today(), end_date=date.today()+timedelta(days=30)))
            conn.execute(metadata.tables["film_genres"].insert().values(film_id=41, genre_id=1))
            conn.execute(metadata.tables["film_formats"].insert().values(film_id=41, format_id=1))
            conn.execute(metadata.tables["food_items"].insert(), [
                dict(id=1,name="Drink",description="",category="DRINK",price=Decimal("12345.67"),is_active=True),
                dict(id=2,name="Combo",description="",category="COMBO",price=Decimal("23456.78"),is_active=False)])
            conn.execute(metadata.tables["combo_items"].insert().values(id=9, combo_id=2, food_item_id=1, quantity=2))
            conn.execute(metadata.tables["showtimes"].insert().values(id=77,film_id=41,format_id=1,room_id=1,
                show_date=date.today()+timedelta(days=5),start_time=time(18),end_time=time(20),status="ACTIVE",
                catalog_binding_id=binding_id,catalog_film_snapshot=fact))
            for name in ("genres", "formats", "films", "food_items", "combo_items"):
                conn.execute(text("SELECT setval(pg_get_serial_sequence(:name,'id'),100000,true)"), {"name":name})
        with pytest.raises(ValueError): transfer(source, catalog_store, apply=True)
        with pytest.raises(ValueError): transfer(source, catalog_store)
        result = transfer(source, catalog_store, apply=True, frozen=True)
        assert result["verified"] and result["copied"] and result["tables"]["schedule_bindings"]["rows"] == 1
        assert transfer(source, catalog_store)["verified"]
        assert not transfer(source, catalog_store, apply=True, frozen=True)["copied"]
        with Session(catalog_store) as db:
            assert db.get(Film, 41).formats == ["2D"]
            binding = db.get(ScheduleBinding, binding_id)
            assert binding.film_snapshot == fact and binding.film_version == 1
            assert db.execute(text("SELECT price FROM food_items WHERE id=1")).scalar_one() == Decimal("12345.67")
            fresh = Film(title="New", duration_minutes=100)
            db.add(fresh)
            db.commit()
            assert fresh.id > 100000
        with pytest.raises(ValueError): transfer(source, catalog_store, apply=True, frozen=True)
    finally:
        source.dispose()
        with root.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()
