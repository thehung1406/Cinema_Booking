import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlmodel import SQLModel,Session,create_engine
from app.models.sales import SalesBase
from app.models.migration_ownership import OwnershipBase,DomainOwnership
from app.models import Role,User,Booking
from app.services import sales_service as sales
from app.repositories.seat_repo import SeatRepository
from app.schemas.booking import BookingCreateRequest
from app.services.booking_service import BookingService
from test_sales_boundary import payload


@pytest.fixture
def sales_race_store():
    url=os.environ.get('TEST_POSTGRES_URL','')
    if 'test' not in url: pytest.skip('Dedicated PostgreSQL required')
    root=create_engine(url); schema='sales_race_'+uuid4().hex
    with root.begin() as conn: conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine=create_engine(url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        SQLModel.metadata.create_all(engine); SalesBase.metadata.create_all(engine); OwnershipBase.metadata.create_all(engine)
        with Session(engine) as db:
            db.add_all([DomainOwnership(domain=d,owner='service' if d=='cinema' else 'monolith') for d in ('cinema','identity','catalog')])
            db.add(Role(id=1,code='USER',name='User')); db.flush()
            db.add(User(id=1,username='race',email='race@example.test',password='unused',role_id=1)); db.commit()
            item=payload(); sales.close(db,item.showtime_id,1); sales.install(db,item,item.digest(),2); sales.open_sales(db,item.showtime_id,1,item.digest(),3)
        yield engine
    finally:
        engine.dispose()
        with root.begin() as conn: conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()


@pytest.mark.parametrize('race',['hold-close','checkout-import'])
def test_sales_gate_serializes_control_against_customer_transactions(sales_race_store,race):
    engine=sales_race_store; item=payload(); barrier=Barrier(2)
    if race=='checkout-import':
        with Session(engine) as db:
            SeatRepository.hold_seat_optimistic(db,item.showtime_id,item.seats[0].id,1); db.commit()
            sales.close(db,item.showtime_id,4)
    def writer(index):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try:
                if race=='hold-close':
                    if index==0: SeatRepository.hold_seat_optimistic(db,item.showtime_id,item.seats[0].id,1); db.commit()
                    else: sales.close(db,item.showtime_id,4)
                elif index==0:
                    BookingService.create_booking(db,BookingCreateRequest(userId=1,showtimeId=item.showtime_id,totalAmount=75000,paymentMethod='VNPAY',seats=[dict(seat_id=item.seats[0].id,price=0)]),1)
                else:
                    changed=item.model_copy(deep=True); changed.sales_version=2
                    sales.install(db,changed,changed.digest(),5)
                return 'ok'
            except HTTPException: db.rollback(); return 'rejected'
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(writer,[0,1]))
    with Session(engine) as db:
        gate=sales.gate(db,item.showtime_id)
        assert not gate.is_open and gate.sales_version==1
        if race=='hold-close':
            assert results[1]=='ok'
            with pytest.raises(HTTPException): SeatRepository.hold_seat_optimistic(db,item.showtime_id,item.seats[0].id,1)
        else:
            assert results==['ok','rejected']
            assert db.scalar(__import__('sqlalchemy').select(Booking)).sales_version==1
