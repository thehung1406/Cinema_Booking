import os
from datetime import date,time,timedelta
from uuid import uuid4
import pytest
from sqlalchemy import create_engine,MetaData,Table,text
from sqlalchemy.orm import Session
from cinema_service.migrate import transfer,TABLES
from cinema_service.models import Showtime,Theater


def test_frozen_copy_verifies_all_five_tables_preserves_ids_snapshots_and_sequence_highwater(cinema_store):
    root=create_engine(os.environ['TEST_POSTGRES_URL']); schema='cinema_copy_'+uuid4().hex
    with root.begin() as conn: conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    source=create_engine(os.environ['TEST_POSTGRES_URL'],connect_args={'options':f'-csearch_path={schema}'})
    try:
        metadata=MetaData()
        for name in TABLES: Table(name,metadata,autoload_with=root,resolve_fks=False)
        metadata.create_all(source)
        fact=dict(id=88,title='Snapshot',catalog_version=1,format_ids=[77],format_name='2D')
        with source.begin() as conn:
            conn.execute(metadata.tables['theaters'].insert().values(id=41,name='Theater',address='Test',city='Test'))
            conn.execute(metadata.tables['cinema_rooms'].insert().values(id=42,theater_id=41,name='Room',capacity=10,status='ACTIVE'))
            conn.execute(metadata.tables['seat_types'].insert().values(id=43,room_id=42,name='Standard',base_price='12345.67'))
            conn.execute(metadata.tables['seats'].insert().values(id=44,room_id=42,seat_type_id=43,seat_name='A1',status='ACTIVE'))
            conn.execute(metadata.tables['showtimes'].insert().values(id=45,room_id=42,film_id=88,format_id=77,
                show_date=date.today()+timedelta(days=5),start_time=time(18),end_time=time(20),status='ACTIVE',catalog_binding_id=str(uuid4()),catalog_film_snapshot=fact))
            for name in TABLES: conn.execute(text("SELECT setval(pg_get_serial_sequence(:name,'id'),3000000,true)"),{'name':name})
        with pytest.raises(ValueError): transfer(source,cinema_store,apply=True)
        result=transfer(source,cinema_store,apply=True,frozen=True)
        assert result['verified'] and result['copied'] and set(result['tables'])==set(TABLES)
        assert transfer(source,cinema_store)['verified']
        assert not transfer(source,cinema_store,apply=True,frozen=True)['copied']
        with Session(cinema_store) as db:
            assert db.get(Showtime,45).catalog_film_snapshot==fact
            assert db.execute(text('SELECT base_price FROM seat_types WHERE id=43')).scalar_one()==__import__('decimal').Decimal('12345.67')
            new=Theater(name='New',address='Test',city='Test'); db.add(new); db.commit()
            assert new.id>3000000
        with pytest.raises(ValueError): transfer(source,cinema_store,apply=True,frozen=True)
    finally:
        source.dispose()
        with root.begin() as conn: conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()
