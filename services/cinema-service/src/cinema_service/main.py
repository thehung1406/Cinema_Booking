from contextlib import asynccontextmanager
from datetime import date, datetime
from secrets import compare_digest
from uuid import uuid4
from zoneinfo import ZoneInfo
import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import Session
from cinema_platform.auth import AuthClient, AuthError
from cinema_platform.logging import service_logger
from .config import Settings
from .models import Theater, CinemaRoom, Seat, SeatType, Showtime, Operation
from .schemas import RoomWrite, SeatWrite, PriceWrite, ShowtimeWrite
from .public_schemas import TheaterRead, CinemaRoomRead, ShowtimeRead, ShowtimeDetailRead, SeatTypeRead, SeatTypeCreate, SeatTypeUpdatePrice
from .clients import Clients
from . import service

PERMISSIONS={"ROOM":"rooms.manage","SEAT":"rooms.manage","PRICE":"seat_types.manage","SHOW":"showtimes.manage",
             "OPEN":"showtimes.manage","CLOSE":"showtimes.manage","PUBLISH":"showtimes.manage"}
MANAGEMENT={"films.manage","rooms.manage","showtimes.manage","seat_types.manage","users.manage","roles.manage","knowledge.manage","reports.view"}


def needed(kind): return PERMISSIONS[kind.split('_')[0]]


def operation_data(op):
    return dict(operation_id=op.id,status=op.status,phase=op.phase,message=op.message,
        room_id=op.room_id,kind=op.kind,result=op.result,created_at=op.created_at,updated_at=op.updated_at)


def create_app(settings=None, *, engine=None, auth_transport=None, read_transport=None):
    settings=settings or Settings(); own_engine=engine is None
    engine=engine or create_engine(settings.database_url,pool_pre_ping=True)
    logger=service_logger("cinema")

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(trust_env=False,transport=auth_transport) as auth_http:
            with httpx.Client(trust_env=False,transport=read_transport) as read_http:
                app.state.auth=AuthClient(auth_http,settings.identity_origin,settings.service_key)
                app.state.clients=Clients(settings,read_http)
                yield
        if own_engine: engine.dispose()

    app=FastAPI(title="Cinema Service",lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.state.engine=engine

    @app.middleware("http")
    async def context(request,call_next):
        response=await call_next(request)
        response.headers["X-Request-ID"]=str(uuid4()); response.headers["X-Service-Name"]="cinema"
        logger.info("method=%s status=%s",request.method,response.status_code)
        return response

    @app.exception_handler(SQLAlchemyError)
    async def db_error(request,exc):
        return JSONResponse({"detail":"Dữ liệu thay đổi hoặc store Cinema chưa sẵn sàng"},status_code=409 if isinstance(exc,IntegrityError) else 503)

    def database():
        with Session(engine) as db: yield db

    def writes():
        if not settings.writes_enabled: raise HTTPException(503,"Cinema đang chuyển dữ liệu")

    def private(x_service_key: str=Header(default="")):
        if len(settings.service_key)<32: raise HTTPException(503,"Cinema service credential is not configured")
        if not compare_digest(x_service_key.encode(),settings.service_key.encode()): raise HTTPException(401,"Invalid service credential")

    async def current(authorization: str=Header(default="")):
        scheme,_,token=authorization.partition(' ')
        if scheme.lower()!='bearer' or not token: raise HTTPException(401,"Bearer token required")
        try: return await app.state.auth.introspect(token)
        except AuthError as exc: raise HTTPException(exc.status_code,"Không thể xác thực Cinema") from exc

    def require(permission):
        async def check(user=Depends(current)):
            if permission not in user.permissions: raise HTTPException(403,"Bạn không có quyền thực hiện chức năng này")
            return user
        return check

    async def management(user=Depends(current)):
        if not MANAGEMENT.intersection(user.permissions): raise HTTPException(403,"Bạn không có quyền truy cập trang quản trị")
        return user

    def submit(db,kind,body,room_id,target_id,user):
        op_id=service.create_operation(db,kind,body,room_id,target_id,user.user_id)
        return JSONResponse({"operation_id":op_id,"status":"PENDING","phase":"CLOSING",
            "message":"Đã nhận tác vụ; đang đóng bán và chờ xử lý hold/đơn hiện có"},status_code=202)

    def page(db,query,offset,limit):
        return {"items":[service.data(r) for r in db.scalars(query.offset(offset).limit(limit))],
                "total":db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))}

    @app.get("/health/live")
    def live(): return {"status":"ok","service":"cinema"}

    @app.get("/health/ready")
    def ready():
        try:
            with engine.connect() as conn: conn.execute(text("SELECT 1 FROM sales_publications LIMIT 0"))
        except SQLAlchemyError: return JSONResponse({"status":"not_ready","service":"cinema"},status_code=503)
        return {"status":"ready","service":"cinema"}

    @app.get("/internal/v1/migration/state",dependencies=[Depends(private)],include_in_schema=False)
    def migration_state(): return {"writes_enabled":settings.writes_enabled}

    @app.get("/theaters/",response_model=list[TheaterRead])
    def theaters(skip:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),db=Depends(database)):
        return list(db.scalars(select(Theater).where(Theater.deleted_at.is_(None)).order_by(Theater.id).offset(skip).limit(limit)))

    @app.get("/theaters/by-film/{film_id}",response_model=list[TheaterRead])
    def theaters_by_film(film_id:int,from_date:date|None=None,db=Depends(database)):
        query=select(Theater).join(CinemaRoom,CinemaRoom.theater_id==Theater.id).join(Showtime,Showtime.room_id==CinemaRoom.id).where(
            Showtime.film_id==film_id,Showtime.status=="ACTIVE",Showtime.deleted_at.is_(None),Showtime.sales_state=="OPEN",
            Showtime.show_date>=(from_date or datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()),CinemaRoom.deleted_at.is_(None),
            CinemaRoom.status=="ACTIVE",Theater.deleted_at.is_(None)).distinct().order_by(Theater.name)
        return list(db.scalars(query))

    @app.get("/theaters/{theater_id}",response_model=TheaterRead)
    def theater(theater_id:int,db=Depends(database)): return service.get(db,Theater,theater_id)

    @app.get("/cinema-rooms/",response_model=list[CinemaRoomRead])
    def rooms(theater_id:int|None=None,skip:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),db=Depends(database)):
        query=select(CinemaRoom).where(CinemaRoom.deleted_at.is_(None))
        if theater_id is not None: query=query.where(CinemaRoom.theater_id==theater_id)
        return list(db.scalars(query.order_by(CinemaRoom.id).offset(skip).limit(limit)))

    @app.get("/cinema-rooms/theater/{theater_id}",response_model=list[CinemaRoomRead])
    def rooms_by_theater(theater_id:int,db=Depends(database)):
        return list(db.scalars(select(CinemaRoom).where(CinemaRoom.theater_id==theater_id,CinemaRoom.deleted_at.is_(None)).order_by(CinemaRoom.id).limit(50)))

    @app.get("/cinema-rooms/{room_id}",response_model=CinemaRoomRead)
    def room(room_id:int,db=Depends(database)): return service.get(db,CinemaRoom,room_id)

    @app.get("/seat-types/room/{room_id}",response_model=list[SeatTypeRead])
    def prices_by_room(room_id:int,db=Depends(database)):
        service.get(db,CinemaRoom,room_id)
        return list(db.scalars(select(SeatType).where(SeatType.room_id==room_id).order_by(SeatType.name)))

    @app.get("/showtimes",response_model=list[ShowtimeRead])
    def shows(film_id:int,theater_id:int,date:date,db=Depends(database)):
        return list(db.scalars(select(Showtime).join(CinemaRoom,CinemaRoom.id==Showtime.room_id).join(Theater,Theater.id==CinemaRoom.theater_id).where(
            Showtime.film_id==film_id,CinemaRoom.theater_id==theater_id,Showtime.show_date==date,Showtime.status=="ACTIVE",Showtime.deleted_at.is_(None),
            Showtime.sales_state=="OPEN",CinemaRoom.deleted_at.is_(None),CinemaRoom.status=="ACTIVE",Theater.deleted_at.is_(None)).order_by(Showtime.start_time)))

    @app.get("/showtimes/{showtime_id}",response_model=ShowtimeDetailRead)
    def show(showtime_id:int,db=Depends(database)):
        s=service.get(db,Showtime,showtime_id); r=service.get(db,CinemaRoom,s.room_id); t=service.get(db,Theater,r.theater_id); f=s.catalog_film_snapshot
        return dict(id=s.id,show_date=s.show_date,start_time=s.start_time,end_time=s.end_time,format=s.format,status=s.status,
            film_id=s.film_id,film_title=f["title"],image=f.get("image"),duration=f.get("duration"),language=f.get("language"),subtitle=f.get("subtitle"),
            room_id=r.id,room_name=r.name,theater_id=t.id,theater_name=t.name,theater_address=t.address)

    @app.get("/admin/catalog")
    def references(user=Depends(management),db=Depends(database)):
        return dict(theaters=[service.data(t) for t in db.scalars(select(Theater).where(Theater.deleted_at.is_(None)).order_by(Theater.name))],
            rooms=[service.data(r) for r in db.scalars(select(CinemaRoom).where(CinemaRoom.deleted_at.is_(None)).order_by(CinemaRoom.name))])

    class TheaterWrite(BaseModel):
        name:str=Field(min_length=1,max_length=100)
        address:str=Field(min_length=1,max_length=255)
        city:str=Field(min_length=1,max_length=50)
        image:str|None=Field(default=None,max_length=255)

    @app.post("/admin/theaters",status_code=201,dependencies=[Depends(writes)])
    def create_theater(body:TheaterWrite,user=Depends(require("rooms.manage")),db=Depends(database)):
        item=Theater(**body.model_dump()); db.add(item); db.commit(); return service.data(item)

    @app.get("/admin/rooms")
    def admin_rooms(q:str=Query("",max_length=100),theater_id:int|None=None,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),user=Depends(require("rooms.manage")),db=Depends(database)):
        query=select(CinemaRoom).where(CinemaRoom.deleted_at.is_(None))
        if q: query=query.where(CinemaRoom.name.icontains(q,autoescape=True))
        if theater_id: query=query.where(CinemaRoom.theater_id==theater_id)
        return page(db,query.order_by(CinemaRoom.id),offset,limit)

    @app.post("/admin/rooms",status_code=201,dependencies=[Depends(writes)])
    def create_room(body:RoomWrite,user=Depends(require("rooms.manage")),db=Depends(database)):
        service.get(db,Theater,body.theater_id,lock=True)
        item=CinemaRoom(**body.model_dump()); db.add(item); db.commit(); return service.data(item)

    @app.put("/admin/rooms/{room_id}",dependencies=[Depends(writes)])
    def update_room(room_id:int,body:RoomWrite,user=Depends(require("rooms.manage")),db=Depends(database)):
        return submit(db,"ROOM_UPDATE",body.model_dump(mode="json"),room_id,room_id,user)

    @app.delete("/admin/rooms/{room_id}",dependencies=[Depends(writes)])
    def delete_room(room_id:int,user=Depends(require("rooms.manage")),db=Depends(database)):
        return submit(db,"ROOM_DELETE",{},room_id,room_id,user)

    @app.get("/admin/rooms/{room_id}/seats")
    def seats(room_id:int,user=Depends(require("rooms.manage")),db=Depends(database)):
        return {"room":service.data(service.get(db,CinemaRoom,room_id)),"seats":[service.data(s) for s in db.scalars(select(Seat).where(Seat.room_id==room_id,Seat.deleted_at.is_(None)).order_by(Seat.seat_name))],
            "seat_types":[service.data(t) for t in db.scalars(select(SeatType).where(SeatType.room_id==room_id).order_by(SeatType.id))]}

    @app.post("/admin/rooms/{room_id}/seats",dependencies=[Depends(writes)])
    def create_seat(room_id:int,body:SeatWrite,user=Depends(require("rooms.manage")),db=Depends(database)):
        return submit(db,"SEAT_CREATE",body.model_dump(mode="json"),room_id,None,user)

    @app.put("/admin/rooms/{room_id}/seats/{seat_id}",dependencies=[Depends(writes)])
    def update_seat(room_id:int,seat_id:int,body:SeatWrite,user=Depends(require("rooms.manage")),db=Depends(database)):
        return submit(db,"SEAT_UPDATE",body.model_dump(mode="json"),room_id,seat_id,user)

    @app.delete("/admin/rooms/{room_id}/seats/{seat_id}",dependencies=[Depends(writes)])
    def delete_seat(room_id:int,seat_id:int,user=Depends(require("rooms.manage")),db=Depends(database)):
        return submit(db,"SEAT_DELETE",{},room_id,seat_id,user)

    @app.get("/admin/showtimes")
    def admin_shows(film_id:int|None=None,room_id:int|None=None,show_date:date|None=None,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),user=Depends(require("showtimes.manage")),db=Depends(database)):
        query=select(Showtime).where(Showtime.deleted_at.is_(None))
        if film_id: query=query.where(Showtime.film_id==film_id)
        if room_id: query=query.where(Showtime.room_id==room_id)
        if show_date: query=query.where(Showtime.show_date==show_date)
        return page(db,query.order_by(Showtime.show_date.desc(),Showtime.start_time),offset,limit)

    @app.post("/admin/showtimes",dependencies=[Depends(writes)])
    def create_show(body:ShowtimeWrite,user=Depends(require("showtimes.manage")),db=Depends(database)):
        return submit(db,"SHOW_CREATE",body.model_dump(mode="json"),body.room_id,None,user)

    @app.put("/admin/showtimes/{showtime_id}",dependencies=[Depends(writes)])
    def update_show(showtime_id:int,body:ShowtimeWrite,user=Depends(require("showtimes.manage")),db=Depends(database)):
        return submit(db,"SHOW_UPDATE",body.model_dump(mode="json"),body.room_id,showtime_id,user)

    @app.delete("/admin/showtimes/{showtime_id}",dependencies=[Depends(writes)])
    def delete_show(showtime_id:int,user=Depends(require("showtimes.manage")),db=Depends(database)):
        return submit(db,"SHOW_DELETE",{},service.get(db,Showtime,showtime_id).room_id,showtime_id,user)

    @app.post("/admin/showtimes/{showtime_id}/sales/{action}",dependencies=[Depends(writes)])
    def sales_action(showtime_id:int,action:str,user=Depends(require("showtimes.manage")),db=Depends(database)):
        if action not in {"open","close","publish"}: raise HTTPException(404,"Thao tác không tồn tại")
        return submit(db,action.upper(),{},service.get(db,Showtime,showtime_id).room_id,showtime_id,user)

    @app.get("/admin/prices")
    def prices(room_id:int|None=None,q:str=Query("",max_length=30),offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),user=Depends(require("seat_types.manage")),db=Depends(database)):
        query=select(SeatType).join(CinemaRoom,CinemaRoom.id==SeatType.room_id).where(CinemaRoom.deleted_at.is_(None))
        if room_id: query=query.where(SeatType.room_id==room_id)
        if q: query=query.where(SeatType.name.icontains(q,autoescape=True))
        return page(db,query.order_by(SeatType.room_id,SeatType.id),offset,limit)

    @app.post("/admin/prices",dependencies=[Depends(writes)])
    def create_price(body:PriceWrite,user=Depends(require("seat_types.manage")),db=Depends(database)):
        return submit(db,"PRICE_CREATE",body.model_dump(mode="json"),body.room_id,None,user)

    @app.put("/admin/prices/{price_id}",dependencies=[Depends(writes)])
    def update_price(price_id:int,body:PriceWrite,user=Depends(require("seat_types.manage")),db=Depends(database)):
        return submit(db,"PRICE_UPDATE",body.model_dump(mode="json"),service.get(db,SeatType,price_id).room_id,price_id,user)

    @app.delete("/admin/prices/{price_id}",dependencies=[Depends(writes)])
    def delete_price(price_id:int,user=Depends(require("seat_types.manage")),db=Depends(database)):
        return submit(db,"PRICE_DELETE",{},service.get(db,SeatType,price_id).room_id,price_id,user)

    @app.post("/seat-types/",dependencies=[Depends(writes)])
    def create_type(body:SeatTypeCreate,user=Depends(require("seat_types.manage")),db=Depends(database)):
        return submit(db,"PRICE_CREATE",PriceWrite.model_validate(body.model_dump()).model_dump(mode="json"),body.room_id,None,user)

    @app.put("/seat-types/{price_id}/price",dependencies=[Depends(writes)])
    def price_update(price_id:int,body:SeatTypeUpdatePrice,user=Depends(require("seat_types.manage")),db=Depends(database)):
        item=service.get(db,SeatType,price_id)
        return submit(db,"PRICE_UPDATE",PriceWrite(room_id=item.room_id,name=item.name,base_price=body.base_price).model_dump(mode="json"),item.room_id,price_id,user)

    @app.delete("/seat-types/{price_id}",dependencies=[Depends(writes)])
    def type_delete(price_id:int,user=Depends(require("seat_types.manage")),db=Depends(database)):
        return submit(db,"PRICE_DELETE",{},service.get(db,SeatType,price_id).room_id,price_id,user)

    @app.get("/admin/cinema-operations")
    def operations(user=Depends(current),db=Depends(database)):
        allowed=[kind for kind,p in PERMISSIONS.items() if p in user.permissions]
        if not allowed: raise HTTPException(403,"Bạn không có quyền xem tác vụ Cinema")
        query=select(Operation).order_by(Operation.created_at.desc()).limit(50)
        return {"items":[operation_data(op) for op in db.scalars(query) if needed(op.kind) in user.permissions]}

    @app.get("/admin/cinema-operations/{operation_id}")
    def operation(operation_id:str,user=Depends(current),db=Depends(database)):
        op=db.get(Operation,operation_id)
        if op is None: raise HTTPException(404,"Tác vụ không tồn tại")
        if needed(op.kind) not in user.permissions: raise HTTPException(403,"Bạn không có quyền xem tác vụ này")
        return operation_data(op)

    class MatchRequest(BaseModel):
        message:str=Field(max_length=2000)

    @app.post("/internal/v1/theaters/matches",dependencies=[Depends(private)],include_in_schema=False)
    def theater_matches(body:MatchRequest,db=Depends(database)):
        import unicodedata
        def folded(s): return ''.join(c for c in unicodedata.normalize('NFD',s.lower().replace('đ','d')) if unicodedata.category(c)!='Mn')
        return [dict(id=t.id,name=t.name) for t in db.scalars(select(Theater).where(Theater.deleted_at.is_(None))) if len(folded(t.name))>2 and folded(t.name) in folded(body.message)]

    return app


def application(): return create_app()
