from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func, and_, text
from sqlalchemy.exc import IntegrityError
from .models import Theater, CinemaRoom, SeatType, Seat, Showtime, Publication, Operation, utcnow
from .contracts import SalesSnapshot
from .schemas import RoomWrite, SeatWrite, PriceWrite, ShowtimeWrite
from .clients import RemoteFailure


def data(row):
    hidden = {"operation_id", "control_epoch"} if isinstance(row,(CinemaRoom,Seat,Showtime)) else set()
    if isinstance(row,(Seat,Showtime)): hidden.add("deleted_at")
    if isinstance(row,Showtime): hidden |= {"catalog_binding_id","catalog_film_snapshot"}
    return jsonable_encoder({c.name:getattr(row,c.name) for c in row.__table__.columns if c.name not in hidden},
                            custom_encoder={__import__('decimal').Decimal:str})


def get(db, model, item_id, *, lock=False):
    query = select(model).where(model.id == item_id)
    if lock: query = query.with_for_update().execution_options(populate_existing=True)
    item = db.scalar(query)
    if item is None or getattr(item,"deleted_at",None): raise HTTPException(404,"Không tìm thấy dữ liệu")
    return item


def room_shows(db, room_id):
    return list(db.scalars(select(Showtime).where(Showtime.room_id==room_id,Showtime.deleted_at.is_(None)).order_by(Showtime.id)))


def snapshot(db, show, version):
    room, theater = get(db,CinemaRoom,show.room_id), None
    theater = get(db,Theater,room.theater_id)
    rows = db.execute(select(Seat,SeatType).join(SeatType,SeatType.id==Seat.seat_type_id)
        .where(Seat.room_id==room.id,Seat.deleted_at.is_(None)).order_by(Seat.id)).all()
    return SalesSnapshot(showtime_id=show.id,sales_version=version,catalog_binding_id=show.catalog_binding_id,
        film_id=show.film_id,format_id=show.format_id,film=show.catalog_film_snapshot,
        room=dict(id=room.id,theater_id=room.theater_id,name=room.name,capacity=room.capacity,room_type=room.room_type,status=room.status),
        theater=dict(id=theater.id,name=theater.name,address=theater.address,city=theater.city),
        show_date=show.show_date,start_time=show.start_time,end_time=show.end_time,status=show.status,
        seat_count=len(rows),seats=[dict(id=s.id,seat_name=s.seat_name,seat_type_id=t.id,seat_type=t.name,price=t.base_price,status=s.status) for s,t in rows])


def may_open(payload):
    item = SalesSnapshot.model_validate(payload)
    return item.status=="ACTIVE" and item.room.status=="ACTIVE" and any(s.status=="ACTIVE" for s in item.seats) and datetime.combine(item.show_date,item.start_time)>datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).replace(tzinfo=None)


def validate_local(db, kind, body, room_id, target_id):
    room=get(db,CinemaRoom,room_id)
    if kind.startswith("SEAT"):
        if room.status!="ACTIVE": raise HTTPException(409,"Phòng không hoạt động")
        if target_id and get(db,Seat,target_id).room_id!=room_id: raise HTTPException(404,"Ghế không thuộc phòng")
        if kind=="SEAT_DELETE": return
        item=SeatWrite.model_validate(body)
        seat_type=get(db,SeatType,item.seat_type_id)
        if seat_type.room_id!=room_id: raise HTTPException(400,"Loại ghế phải thuộc phòng đang chọn")
        count=db.scalar(select(func.count()).select_from(Seat).where(Seat.room_id==room_id,Seat.deleted_at.is_(None)))
        if not target_id and count>=room.capacity: raise HTTPException(409,"Phòng đã đủ sức chứa")
        if db.scalar(select(Seat.id).where(Seat.room_id==room_id,Seat.seat_name==item.seat_name,Seat.deleted_at.is_(None),Seat.id!=(target_id or 0))):
            raise HTTPException(409,"Vị trí ghế đã tồn tại")
    elif kind=="ROOM_UPDATE":
        item=RoomWrite.model_validate(body); get(db,Theater,item.theater_id)
        count=db.scalar(select(func.count()).select_from(Seat).where(Seat.room_id==room_id,Seat.deleted_at.is_(None)))
        if item.capacity<count: raise HTTPException(409,"Sức chứa không được nhỏ hơn số ghế hiện có")
        if item.theater_id!=room.theater_id and room_shows(db,room_id): raise HTTPException(409,"Phòng đã có lịch; không thể chuyển rạp")
        if db.scalar(select(CinemaRoom.id).where(CinemaRoom.theater_id==item.theater_id,CinemaRoom.name==item.name,CinemaRoom.deleted_at.is_(None),CinemaRoom.id!=room_id)):
            raise HTTPException(409,"Tên phòng đã tồn tại")
        now=datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).replace(tzinfo=None)
        if item.status!="ACTIVE" and any(s.status=="ACTIVE" and datetime.combine(s.show_date,s.end_time)>now for s in room_shows(db,room_id)):
            raise HTTPException(409,"Phòng có lịch chưa kết thúc; cần xử lý lịch trước bảo trì")
    elif kind=="ROOM_DELETE":
        if room_shows(db,room_id): raise HTTPException(409,"Phòng đã có lịch chiếu")
    elif kind.startswith("PRICE"):
        if target_id and get(db,SeatType,target_id).room_id!=room_id: raise HTTPException(400,"Không thể chuyển loại ghế sang phòng khác")
        if kind=="PRICE_DELETE":
            if db.scalar(select(Seat.id).where(Seat.seat_type_id==target_id).limit(1)): raise HTTPException(409,"Loại ghế còn được sử dụng")
        else:
            item=PriceWrite.model_validate(body)
            if item.room_id!=room_id: raise HTTPException(400,"Sai phòng của loại ghế")
            if db.scalar(select(SeatType.id).where(SeatType.room_id==room_id,SeatType.name==item.name,SeatType.id!=(target_id or 0))): raise HTTPException(409,"Tên loại ghế đã tồn tại")
    elif kind in {"SHOW_CREATE","SHOW_UPDATE"}:
        item=ShowtimeWrite.model_validate(body)
        if item.room_id!=room_id: raise HTTPException(409,"Di chuyển lịch sang phòng khác cần tác vụ riêng")
        if room.status!="ACTIVE": raise HTTPException(409,"Phòng không hoạt động")
        if datetime.combine(item.show_date,item.start_time)<=datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).replace(tzinfo=None): raise HTTPException(400,"Suất chiếu phải ở tương lai")
        if db.scalar(select(Showtime.id).where(Showtime.room_id==room_id,Showtime.deleted_at.is_(None),Showtime.status!="CANCELLED",
            Showtime.show_date==item.show_date,Showtime.start_time<item.end_time,Showtime.end_time>item.start_time,Showtime.id!=(target_id or 0))): raise HTTPException(409,"Lịch chiếu bị trùng trong phòng")
    elif kind in {"SHOW_DELETE","OPEN","CLOSE","PUBLISH"}:
        show=get(db,Showtime,target_id)
        if show.room_id!=room_id: raise HTTPException(404,"Lịch không thuộc phòng")
        if kind=="OPEN":
            pub=db.get(Publication,(show.id,show.sales_version))
            if pub is None or not pub.acknowledged or not may_open(pub.snapshot): raise HTTPException(409,"Suất chưa có cấu hình có thể mở bán")


def create_operation(db, kind, body, room_id, target_id, actor_id):
    room_ids={room_id}
    if kind=="SHOW_UPDATE": room_ids.add(get(db,Showtime,target_id).room_id)
    rooms=[get(db,CinemaRoom,i,lock=True) for i in sorted(room_ids)]
    if any(room.operation_id for room in rooms): raise HTTPException(409,"Phòng đang có tác vụ chưa hoàn tất")
    validate_local(db,kind,body,room_id,target_id)
    op=Operation(id=str(uuid4()),room_id=room_id,kind=kind,target_id=target_id,payload=body,
        progress={"rooms":sorted(room_ids)},phase="CLOSING",status="PENDING",message="Đang đóng nhận giữ ghế mới",actor_id=actor_id)
    db.add(op)
    for room in rooms: room.operation_id=op.id
    db.commit()
    return op.id


def next_epoch(db, show, progress, key):
    if key not in progress:
        show.control_epoch+=1; progress[key]=show.control_epoch
    return progress[key]


def execute(engine, op_id, clients):
    # Session advisory lock survives phase commits and is released on crash.
    from sqlalchemy.orm import Session
    with engine.connect() as lock_conn:
        acquired=lock_conn.execute(text("SELECT pg_try_advisory_lock(hashtextextended(:id,0))"),{"id":op_id}).scalar_one()
        lock_conn.commit()
        if not acquired: return
        try:
            with Session(bind=lock_conn) as db:
                op=db.get(Operation,op_id)
                if op is None or op.status in {"DONE","FAILED"}: return
                try:
                    progress=dict(op.progress)
                    if op.phase=="COMPENSATING":
                        binding_id=progress.get("binding_id")
                        if binding_id:
                            clients.reference(binding_id,"release","cinema-operation:"+op.id)
                        fail(db,op,progress.get("failure","Tác vụ không thể hoàn tất")); return
                    if "shows" not in progress:
                        shows=[] if op.kind=="SHOW_CREATE" else ([get(db,Showtime,op.target_id)] if op.kind in {"SHOW_UPDATE","SHOW_DELETE","OPEN","CLOSE","PUBLISH"} else room_shows(db,op.room_id))
                        progress["shows"]=[s.id for s in shows]
                        op.progress=progress; db.commit()
                    shows=[db.get(Showtime,i) for i in progress["shows"]]
                    if op.phase=="CLOSING":
                        for show in shows:
                            epoch=next_epoch(db,show,progress,f"close:{show.id}")
                            show.sales_state="CLOSING"; op.progress=dict(progress); db.commit()
                            clients.close(show.id,epoch)
                            show.sales_state="CLOSED"; db.commit()
                        if op.kind=="CLOSE":
                            finish(db,op,{"id":op.target_id,"sales_state":"CLOSED"}); return
                        op.phase="DRAINING"; db.commit()
                    if op.phase=="DRAINING":
                        if op.kind!="OPEN":
                            for show in shows:
                                state=clients.state(show.id,op.target_id if op.kind.startswith("SEAT") else None)
                                if state["live_holds"] or state["pending_bookings"]:
                                    op.status="WAITING"; op.message="Đang chờ hold hoặc đơn đang xử lý kết thúc"; op.updated_at=utcnow(); db.commit(); return
                                if op.kind in {"SHOW_UPDATE","SHOW_DELETE"} and state["bookings"]:
                                    raise HTTPException(409,"Lịch đã có đơn; không thể sửa hoặc xóa")
                                if op.kind in {"SEAT_UPDATE","SEAT_DELETE"} and (state["seat_references"] or op.target_id in state.get("booked_seat_ids",[])):
                                    raise HTTPException(409,"Ghế đã có đơn/vé; không thể sửa hoặc xóa")
                        op.phase="APPLYING"; op.status="PENDING"; db.commit()
                    if op.phase=="APPLYING":
                        validate_local(db,op.kind,op.payload,op.room_id,op.target_id)
                        if op.kind in {"SHOW_CREATE","SHOW_UPDATE"}:
                            if "binding_id" not in progress:
                                progress["binding_id"]=str(uuid4()); op.progress=dict(progress); db.commit()
                            try:
                                binding=clients.catalog("POST","/schedule-bindings",json={"id":progress["binding_id"],**{k:v for k,v in op.payload.items() if k!="room_id"}})
                            except RemoteFailure as exc:
                                if exc.status in {400,404,409,422}: raise HTTPException(409,str(exc)) from exc
                                raise
                            if binding.get("id")!=progress["binding_id"] or binding.get("film_snapshot",{}).get("id")!=op.payload["film_id"]:
                                raise RemoteFailure(503,"Sai tham chiếu Catalog")
                            progress["binding"]=binding
                        result=apply_mutation(db,op,progress)
                        op.result=jsonable_encoder(result); op.progress=dict(progress)
                        op.phase="PUBLISHING"
                        shows=[s for s in room_shows(db,op.room_id)] if op.kind not in {"SHOW_CREATE","SHOW_UPDATE","SHOW_DELETE","OPEN","PUBLISH"} else [db.get(Showtime,op.target_id)]
                        progress=dict(op.progress); progress["shows"]=[s.id for s in shows]
                        for show in shows:
                            if op.kind=="OPEN": continue
                            version=show.sales_version+1
                            published=snapshot(db,show,version)
                            db.add(Publication(showtime_id=show.id,sales_version=version,digest=published.digest(),snapshot=published.model_dump(mode="json")))
                            show.sales_version=version; show.sales_state="PUBLISHING"
                        op.progress=dict(progress); db.commit()
                    if op.phase=="PUBLISHING":
                        progress=dict(op.progress)
                        for show_id in progress["shows"]:
                            show=db.get(Showtime,show_id)
                            pub=db.get(Publication,(show.id,show.sales_version))
                            if pub is None: raise RemoteFailure(503,"Chưa có cấu hình công bố")
                            if not pub.acknowledged:
                                epoch=next_epoch(db,show,progress,f"import:{show.id}"); op.progress=dict(progress); db.commit()
                                clients.install(pub.snapshot,epoch)
                                pub.acknowledged=True; db.commit()
                            if op.kind=="OPEN" and not may_open(pub.snapshot): raise HTTPException(409,"Suất không còn có thể mở bán")
                            if may_open(pub.snapshot):
                                epoch=next_epoch(db,show,progress,f"open:{show.id}"); op.progress=dict(progress); db.commit()
                                clients.open(pub.snapshot,epoch)
                                show.sales_state="OPEN"
                            else: show.sales_state="CLOSED"
                            db.commit()
                        op.phase="CATALOG_FINALIZE"; db.commit()
                    if op.phase=="CATALOG_FINALIZE":
                        progress=dict(op.progress)
                        for show_id in progress["shows"]:
                            show=db.get(Showtime,show_id)
                            if show.catalog_binding_id:
                                action="release" if show.deleted_at else "confirm"
                                clients.reference(show.catalog_binding_id,action,"cinema-showtime:"+str(show.id))
                        old=progress.get("old_binding_id")
                        if old and old!=progress.get("binding_id"):
                            clients.reference(old,"release","cinema-showtime:"+str(op.target_id))
                        finish(db,op,op.result or {"id":op.target_id,"sales_state":"OPEN"})
                except HTTPException as exc:
                    db.rollback(); op=db.get(Operation,op_id)
                    progress=dict(op.progress)
                    if progress.get("binding_id") and op.phase=="APPLYING":
                        progress["failure"]=str(exc.detail)[:500]; op.progress=progress
                        op.phase="COMPENSATING"; op.status="RETRY"; op.message="Đang thu hồi tham chiếu cấu hình chưa áp dụng"; db.commit()
                    else: fail(db,op,str(exc.detail)[:500])
                except (RemoteFailure,IntegrityError) as exc:
                    db.rollback(); op=db.get(Operation,op_id)
                    op.status="RETRY"; op.message=str(exc)[:300] if isinstance(exc,RemoteFailure) else "Dữ liệu thay đổi; cần kiểm tra tác vụ"
                    op.updated_at=utcnow(); db.commit()
        finally:
            lock_conn.execute(text("SELECT pg_advisory_unlock(hashtextextended(:id,0))"),{"id":op_id}); lock_conn.commit()


def fail(db,op,message):
    op.status="FAILED"; op.message=message; op.updated_at=utcnow()
    for room_id in op.progress.get("rooms",[op.room_id]): db.get(CinemaRoom,room_id).operation_id=None
    db.commit()


def finish(db,op,result):
    if "DELETE" not in op.kind:
        model = Seat if op.kind.startswith("SEAT") else SeatType if op.kind.startswith("PRICE") else CinemaRoom if op.kind.startswith("ROOM") else Showtime
        item=db.get(model,op.target_id or op.room_id)
        if item is not None: result=data(item)
    op.status="DONE"; op.phase="DONE"; op.message="Đã hoàn tất và xác nhận cấu hình bán vé"; op.result=result; op.updated_at=utcnow()
    for room_id in op.progress.get("rooms",[op.room_id]): db.get(CinemaRoom,room_id).operation_id=None
    db.commit()


def apply_mutation(db,op,progress):
    kind, body, target=op.kind,op.payload,op.target_id
    if kind in {"SHOW_CREATE","SHOW_UPDATE"}:
        item=get(db,Showtime,target) if target else Showtime()
        if target: progress["old_binding_id"]=item.catalog_binding_id
        for key,value in ShowtimeWrite.model_validate(body).model_dump().items(): setattr(item,key,value)
        item.catalog_binding_id=progress["binding"]["id"]; item.catalog_film_snapshot=progress["binding"]["film_snapshot"]
        db.add(item); db.flush(); op.target_id=item.id
    elif kind=="SHOW_DELETE":
        item=get(db,Showtime,target); item.deleted_at=utcnow(); item.status="CANCELLED"
    elif kind.startswith("SEAT"):
        item=get(db,Seat,target) if target else Seat(room_id=op.room_id)
        if kind=="SEAT_DELETE":
            db.delete(item); return {"message":"Đã xóa thành công"}
        else:
            for key,value in SeatWrite.model_validate(body).model_dump().items(): setattr(item,key,value)
        db.add(item); db.flush(); op.target_id=item.id
    elif kind.startswith("PRICE"):
        item=get(db,SeatType,target) if target else SeatType()
        if kind=="PRICE_DELETE":
            # Soft-deleted physical seats still retain their historical type.
            if db.scalar(select(Seat.id).where(Seat.seat_type_id==target).limit(1)): raise HTTPException(409,"Loại ghế còn tham chiếu lịch sử")
            result={"message":"Đã xóa loại ghế"}; db.delete(item); return result
        for key,value in PriceWrite.model_validate(body).model_dump().items(): setattr(item,key,value)
        db.add(item); db.flush(); op.target_id=item.id
    elif kind=="ROOM_UPDATE":
        item=get(db,CinemaRoom,op.room_id)
        for key,value in RoomWrite.model_validate(body).model_dump().items(): setattr(item,key,value)
    elif kind=="ROOM_DELETE":
        item=get(db,CinemaRoom,op.room_id); item.deleted_at=utcnow()
    else: item=get(db,Showtime,target)
    return data(item) if "DELETE" not in kind else {"message":"Đã xóa thành công"}
