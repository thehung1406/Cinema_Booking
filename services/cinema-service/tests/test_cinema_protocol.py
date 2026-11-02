from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier
from uuid import uuid4
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError,DBAPIError
from cinema_service.models import Theater,CinemaRoom,SeatType,Seat,Showtime,Publication,Operation
from cinema_service import service
from cinema_service.clients import Clients,RemoteFailure
from cinema_service.config import Settings
from cinema_service.main import create_app


def seed(engine):
    with Session(engine) as db:
        db.add(Theater(id=1,name="Test cinema",address="Test",city="Test")); db.flush()
        db.add(CinemaRoom(id=1,theater_id=1,name="Room",capacity=1,status="ACTIVE")); db.flush()
        db.add(SeatType(id=1,room_id=1,name="Standard",base_price=75000)); db.flush()
        db.add(Seat(id=1,room_id=1,seat_type_id=1,seat_name="A1",status="ACTIVE"))
        db.add(Showtime(id=1,film_id=101,format_id=201,room_id=1,show_date=date.today()+timedelta(days=5),
            start_time=__import__('datetime').time(18),end_time=__import__('datetime').time(20),
            catalog_binding_id=str(uuid4()),catalog_film_snapshot={"id":101,"title":"Independent film","catalog_version":1,"format_ids":[201],"format_name":"2D"}))
        db.commit()


class Peer:
    def __init__(self):
        self.holds=0; self.bookings=0; self.refs=0; self.fail_import=False; self.opened=[]; self.versions=[]; self.closed=[]
    def close(self,show_id,epoch): self.closed.append((show_id,epoch))
    def state(self,*args): return dict(live_holds=self.holds,pending_bookings=0,bookings=self.bookings,seat_references=self.refs,booked_seat_ids=[])
    def install(self,payload,epoch):
        self.versions.append(payload["sales_version"])
        if self.fail_import: raise RemoteFailure(503,"Lost ACK")
    def open(self,payload,epoch): self.opened.append((payload["sales_version"],epoch))
    def catalog(self,*args,**kwargs): return {}
    def reference(self,*args): return {}


def test_operation_drains_holds_retries_exact_publication_and_opens_only_after_ack(cinema_store):
    seed(cinema_store); peer=Peer(); peer.holds=1
    with Session(cinema_store) as db:
        op_id=service.create_operation(db,"PRICE_UPDATE",dict(room_id=1,name="Standard",base_price="90000.00"),1,1,91)
    service.execute(cinema_store,op_id,peer)
    with Session(cinema_store) as db:
        op=db.get(Operation,op_id)
        assert (op.status,op.phase)==("WAITING","DRAINING")
        assert db.get(SeatType,1).base_price==75000
        with pytest.raises(HTTPException): service.create_operation(db,"CLOSE",{},1,1,91)
    peer.holds=0; peer.fail_import=True
    service.execute(cinema_store,op_id,peer)
    with Session(cinema_store) as db:
        assert db.get(Operation,op_id).status=="RETRY"
        pub=db.get(Publication,(1,1)); digest=pub.digest
        assert pub.snapshot["seats"][0]["price"]=="90000.00" and not pub.acknowledged
    assert not peer.opened
    peer.fail_import=False; service.execute(cinema_store,op_id,peer)
    with Session(cinema_store) as db:
        assert db.get(Operation,op_id).status=="DONE"
        assert db.get(CinemaRoom,1).operation_id is None
        assert db.get(Publication,(1,1)).digest==digest
        assert db.get(Showtime,1).sales_state=="OPEN"
    assert peer.versions==[1,1] and len(peer.opened)==1
    service.execute(cinema_store,op_id,peer)
    assert len(peer.opened)==1


def test_paid_or_referenced_seat_cannot_be_disabled_after_drain(cinema_store):
    seed(cinema_store); peer=Peer(); peer.holds=1
    with Session(cinema_store) as db:
        op_id=service.create_operation(db,"SEAT_UPDATE",dict(seat_name="A1",seat_type_id=1,status="INACTIVE"),1,1,91)
    service.execute(cinema_store,op_id,peer)
    peer.holds=0; peer.refs=1; peer.bookings=1
    service.execute(cinema_store,op_id,peer)
    with Session(cinema_store) as db:
        assert db.get(Operation,op_id).status=="FAILED"
        assert db.get(Seat,1).status=="ACTIVE"
        assert db.get(Showtime,1).sales_state=="CLOSED"
    assert not peer.opened


@pytest.mark.parametrize("kind",["capacity","schedule"])
def test_database_serializes_concurrent_constraints(cinema_store,kind):
    seed(cinema_store)
    if kind=="capacity":
        with cinema_store.begin() as conn: conn.execute(text("DELETE FROM seats"))
    barrier=Barrier(2)
    def writer(i):
        with Session(cinema_store) as db:
            barrier.wait(timeout=10)
            try:
                if kind=="capacity": db.add(Seat(room_id=1,seat_type_id=1,seat_name=f"A{i}",status="ACTIVE"))
                else: db.add(Showtime(film_id=101,format_id=201,room_id=1,show_date=date.today()+timedelta(days=6),start_time=__import__('datetime').time(18),end_time=__import__('datetime').time(20)))
                db.commit(); return "ok"
            except IntegrityError: db.rollback(); return "rejected"
    with ThreadPoolExecutor(max_workers=2) as pool: assert sorted(pool.map(writer,[1,2]))==["ok","rejected"]


def test_api_auth_accepted_state_and_open_validation(cinema_store):
    seed(cinema_store)
    state={"user_id":91,"role":"ADMIN","permissions":["rooms.manage","showtimes.manage","seat_types.manage"],"is_active":True}
    settings=Settings(writes_enabled=True)
    app=create_app(settings,engine=cinema_store,auth_transport=httpx.MockTransport(lambda r:httpx.Response(200,json=state)))
    with TestClient(app) as client:
        assert client.get('/admin/rooms').status_code==401
        headers={"Authorization":"Bearer test"}
        assert client.get('/admin/rooms',headers=headers).status_code==200
        assert client.post('/admin/showtimes/1/sales/open',headers=headers).status_code==409
        result=client.put('/admin/prices/1',headers=headers,json=dict(room_id=1,name="Standard",base_price=90000))
        assert result.status_code==202 and result.json()["status"]=="PENDING"
        assert client.get('/admin/cinema-operations/'+result.json()["operation_id"],headers=headers).json()["status"]=="PENDING"
        state["permissions"]=[]
        assert client.get('/admin/cinema-operations',headers=headers).status_code==403


@pytest.mark.parametrize("reply",[{"acknowledged":True},{"acknowledged":False},{"acknowledged":True,"epoch":2,"digest":"bad","sales_version":1}])
def test_missing_or_incorrect_ack_never_passes(cinema_store,reply):
    seed(cinema_store)
    with Session(cinema_store) as db: payload=service.snapshot(db,db.get(Showtime,1),1).model_dump(mode="json")
    settings=Settings()
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=reply))) as http:
        with pytest.raises(RemoteFailure): Clients(settings,http).install(payload,2)


def test_database_publication_immutability_and_intra_room_type(cinema_store):
    seed(cinema_store)
    with Session(cinema_store) as db:
        pub=service.snapshot(db,db.get(Showtime,1),1)
        db.add(Publication(showtime_id=1,sales_version=1,snapshot=pub.model_dump(mode="json"),digest=pub.digest())); db.commit()
    with pytest.raises(DBAPIError):
        with cinema_store.begin() as conn: conn.execute(text("UPDATE sales_publications SET digest='changed'"))
    with Session(cinema_store) as db:
        db.add(CinemaRoom(id=2,theater_id=1,name="Other",capacity=10,status="ACTIVE")); db.commit()
    with pytest.raises(IntegrityError):
        with Session(cinema_store) as db:
            db.add(Seat(room_id=2,seat_type_id=1,seat_name="B1",status="ACTIVE")); db.commit()


def test_terminal_bind_rejection_seals_operation_then_releases_reservation(cinema_store):
    seed(cinema_store)
    class Rejected(Peer):
        def catalog(self,*args,**kwargs): raise RemoteFailure(400,"Phim không còn hỗ trợ cấu hình")
        def reference(self,*args): self.released=args
    peer=Rejected()
    with Session(cinema_store) as db:
        body=dict(film_id=101,format_id=201,room_id=1,show_date=(date.today()+timedelta(days=6)).isoformat(),start_time="18:00",end_time="20:00")
        op_id=service.create_operation(db,"SHOW_CREATE",body,1,None,91)
    service.execute(cinema_store,op_id,peer)
    with Session(cinema_store) as db:
        op=db.get(Operation,op_id)
        assert (op.phase,op.status)==("COMPENSATING","RETRY")
        assert db.get(CinemaRoom,1).operation_id==op_id
        binding_id=op.progress['binding_id']
    service.execute(cinema_store,op_id,peer)
    assert peer.released==(binding_id,"release","cinema-operation:"+op_id)
    with Session(cinema_store) as db:
        assert db.get(Operation,op_id).status=="FAILED" and db.get(CinemaRoom,1).operation_id is None


def test_bootstrap_retry_after_lost_open_ack_does_not_replay_older_close(cinema_store):
    from sqlalchemy import create_engine
    from cinema_service.migrate import bootstrap
    seed(cinema_store)
    schema='bootstrap_'+uuid4().hex
    with cinema_store.begin() as conn: conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    source=create_engine(cinema_store.url,connect_args={'options':f'-csearch_path={schema}'})
    with source.begin() as conn:
        conn.execute(text("CREATE TABLE domain_ownership(domain text,owner text); INSERT INTO domain_ownership VALUES ('cinema','maintenance')"))
        conn.execute(text("CREATE TABLE bookings(booking_status text,expires_at timestamptz,booking_date timestamptz,sales_version integer)"))
        conn.execute(text("CREATE TABLE seat_status(status text,hold_expired_at timestamptz,sales_version integer,hold_by_user_id integer)"))
    class LostOpen(Peer):
        def open(self,payload,epoch):
            super().open(payload,epoch)
            if len(self.opened)==1: raise RemoteFailure(503,"Lost open response")
    peer=LostOpen()
    try:
        with pytest.raises(ValueError): bootstrap(source,cinema_store,peer)
        assert bootstrap(source,cinema_store,peer)==1
        assert peer.closed==[(1,1)]
        assert len(peer.opened)==2 and peer.opened[0]==peer.opened[1]
        with Session(cinema_store) as db: assert db.get(Operation,'bootstrap-1').status=='DONE'
    finally:
        source.dispose()
        with cinema_store.begin() as conn: conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
