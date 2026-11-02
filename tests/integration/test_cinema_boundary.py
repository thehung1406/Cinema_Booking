from datetime import date,timedelta
from pathlib import Path
import sys
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select,text
from sqlalchemy.orm import Session

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Backend/tests'))
sys.path.insert(0,str(ROOT/'services/cinema-service/tests'))
sys.path.insert(0,str(ROOT/'services/catalog-service/tests'))
from test_normalized_schema import pg,catalog,provider,provider_params
from cinema_support import cinema_store
from catalog_support import catalog_store,catalog_settings,catalog_client
from cinema_service.config import Settings
from cinema_service.main import create_app
from cinema_service.clients import Clients
from cinema_service.service import execute
from cinema_service.models import Operation,Showtime as OwnerShow,Seat as OwnerSeat
from app.core.config import settings
from app.core.database import get_session
from app.router.internal_sales import router
from app.models import Booking,Showtime,Seat
from app.schemas.booking import BookingCreateRequest
from app.services.seat_service import SeatService
from app.services.booking_service import BookingService
from app.services.payment_service import PaymentService
from app.repositories.payment_repo import PaymentRepository
from app.repositories.booking_repo import BookingRepository


def test_cinema_creates_new_entities_publishes_via_private_api_and_booking_works_without_mirrors(
        pg,catalog,provider,cinema_store,catalog_client,catalog_settings,monkeypatch):
    pg.execute(text("UPDATE domain_ownership SET owner='service' WHERE domain='cinema'")); pg.commit()
    monkeypatch.setattr(settings,"CINEMA_STORAGE_OWNER","service")
    monkeypatch.setattr(settings,"NOTIFICATION_TRANSPORT","events")
    monkeypatch.setattr("app.services.seat_service.SeatLockManager.lock_seat",lambda **kw:True)
    source=FastAPI(); source.include_router(router)
    source.dependency_overrides[get_session]=lambda:pg
    cfg=Settings(writes_enabled=True)
    auth=dict(user_id=91,role="ADMIN",permissions=["rooms.manage","showtimes.manage","seat_types.manage"],is_active=True)
    app=create_app(cfg,engine=cinema_store,auth_transport=httpx.MockTransport(lambda r:httpx.Response(200,json=auth)))
    with cinema_store.begin() as conn:
        for table in ('theaters','cinema_rooms','seat_types','seats','showtimes'):
            conn.execute(text("SELECT setval(pg_get_serial_sequence(:name,'id'),2000000,true)"),{"name":table})
    headers={"Authorization":"Bearer test"}
    with TestClient(source) as booking_api,TestClient(app) as client:
        def request(req):
            target=booking_api if req.url.path.startswith('/internal/v1/sales') else catalog_client
            response=target.request(req.method,req.url.path+('?' + req.url.query.decode() if req.url.query else ''),content=req.content,headers=dict(req.headers))
            return httpx.Response(response.status_code,json=response.json())
        with httpx.Client(transport=httpx.MockTransport(request)) as http:
            peer=Clients(cfg,http)
            theater=client.post('/admin/theaters',headers=headers,json=dict(name="Independent theater",address="Test",city="Test")).json()
            room=client.post('/admin/rooms',headers=headers,json=dict(theater_id=theater['id'],name="Independent room",capacity=10,status="ACTIVE")).json()
            def complete(response):
                assert response.status_code==202,response.text
                op_id=response.json()['operation_id']; execute(cinema_store,op_id,peer)
                op=client.get('/admin/cinema-operations/'+op_id,headers=headers).json()
                assert op['status']=='DONE',op
                return op['result']
            price=complete(client.post('/admin/prices',headers=headers,json=dict(room_id=room['id'],name="Standard",base_price="75000.00")))
            seat=complete(client.post(f"/admin/rooms/{room['id']}/seats",headers=headers,json=dict(seat_type_id=price['id'],seat_name="A1")))
            show=complete(client.post('/admin/showtimes',headers=headers,json=dict(film_id=1,format_id=1,room_id=room['id'],show_date=(date.today()+timedelta(days=5)).isoformat(),start_time="18:00",end_time="20:00")))
            assert show['sales_version']==1 and show['sales_state']=='OPEN'
            assert pg.get(Showtime,show['id']) is None and pg.get(Seat,seat['id']) is None
            SeatService.hold_seats(pg,show['id'],[seat['id']],catalog['user'].id)
            change=client.put(f"/admin/prices/{price['id']}",headers=headers,json=dict(room_id=room['id'],name="Standard",base_price="90000.00"))
            op_id=change.json()['operation_id']; execute(cinema_store,op_id,peer)
            assert client.get('/admin/cinema-operations/'+op_id,headers=headers).json()['status']=='WAITING'
            created=BookingService.create_booking(pg,BookingCreateRequest(userId=catalog['user'].id,showtimeId=show['id'],totalAmount=75000,paymentMethod="VNPAY",seats=[dict(seat_id=seat['id'],price=0)]),catalog['user'].id)
            booking=pg.get(Booking,created.bookingId)
            attempt=PaymentRepository.create_attempt(pg,booking)
            assert PaymentService.confirm_vnpay_payment(pg,booking.id,"00",provider_params(attempt))['status']=='success'
            execute(cinema_store,op_id,peer)
            assert client.get('/admin/cinema-operations/'+op_id,headers=headers).json()['status']=='DONE'
            with Session(cinema_store) as db:
                assert db.get(OwnerShow,show['id']).sales_version==2
                assert db.get(OwnerSeat,seat['id']).seat_name=='A1'
            assert BookingRepository.get_booking_with_details(pg,booking.id)['seats'][0]['price']==75000
