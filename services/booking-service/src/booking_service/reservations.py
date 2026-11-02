from datetime import datetime,timedelta,timezone
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlmodel import select
from .models import Reservation,SeatStatus,Booking
from .sales import configuration,gate
from .config import settings

def now(): return datetime.now(timezone.utc)

def rows(db,show_id,ids=None):
    query=select(SeatStatus).where(SeatStatus.showtime_id==show_id)
    if ids is not None: query=query.where(SeatStatus.seat_id.in_(ids))
    return list(db.exec(query.order_by(SeatStatus.seat_id).with_for_update().execution_options(populate_existing=True)))

def expire_show(db,show_id):
    # All mutating flows take gate -> reservation/booking -> seats (ascending ID).
    gate(db,show_id,lock=True)
    stamp=now(); count=0
    expired=list(db.exec(select(Reservation).where(Reservation.showtime_id==show_id,Reservation.status.in_(['ACTIVE','CHECKOUT']),Reservation.expires_at<=stamp).order_by(Reservation.id).with_for_update()))
    for reservation in expired:
        booking=db.exec(select(Booking).where(Booking.reservation_id==reservation.id).with_for_update()).first()
        if booking and booking.booking_status=='PENDING':
            booking.booking_status='EXPIRED'
            if booking.payment_status=='PENDING': booking.payment_status='FAILED'
            from .events import checkout_event
            checkout_event(db,booking,"BookingExpired.v1")
        reservation.status='EXPIRED'; count+=1
        for seat in rows(db,show_id,reservation.seat_ids):
            if seat.status=='HOLD' and seat.reservation_id==reservation.id:
                seat.status='AVAILABLE'; seat.hold_by_user_id=None; seat.hold_expired_at=None; seat.version+=1; seat.updated_at=stamp
    db.flush(); return count

def hold(db,show_id,seat_ids,user_id,reservation_id=None):
    ids=sorted(set(seat_ids))
    if len(ids)!=len(seat_ids) or not ids or len(ids)>20 or min(ids)<=0: raise HTTPException(400,'Danh sách ghế không hợp lệ')
    config=configuration(db,show_id,lock=True,require_open=True)
    expire_show(db,show_id)
    if config.status!='ACTIVE' or datetime.combine(config.show_date,config.start_time)<=datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).replace(tzinfo=None): raise HTTPException(409,'Suất đã bắt đầu')
    seats={s['id']:s for s in config.snapshot['seats']}
    if any(i not in seats or seats[i]['status']!='ACTIVE' for i in ids): raise HTTPException(409,'Ghế không thể giữ')
    reservation=db.exec(select(Reservation).where(Reservation.user_id==user_id,Reservation.showtime_id==show_id,Reservation.status.in_(['ACTIVE','CHECKOUT'])).with_for_update()).first()
    if reservation_id and (reservation is None or reservation.id!=reservation_id): raise HTTPException(409,'Reservation đã bị thay thế hoặc hết hạn')
    if reservation and (reservation.status!='ACTIVE' or reservation.sales_version!=config.sales_version): raise HTTPException(409,'Reservation đang checkout hoặc thuộc phiên bản khác')
    current={r.seat_id:r for r in rows(db,show_id,ids)}
    if any(r.status=='BOOKED' or (r.status=='HOLD' and r.hold_expired_at>now() and (reservation is None or r.reservation_id!=reservation.id)) for r in current.values()): raise HTTPException(409,'Ghế đang được giữ hoặc đã bán')
    if reservation is None:
        reservation=Reservation(id=str(uuid4()),user_id=user_id,showtime_id=show_id,sales_version=config.sales_version,seat_ids=[],expires_at=now()+timedelta(seconds=settings.hold_seconds))
        db.add(reservation); db.flush()
    if len(set(reservation.seat_ids)|set(ids))>20: raise HTTPException(400,'Tối đa 20 ghế mỗi reservation')
    reservation.seat_ids=sorted(set(reservation.seat_ids)|set(ids)); db.add(reservation)
    for seat_id in ids:
        seat=current.get(seat_id)
        if seat is None: seat=SeatStatus(showtime_id=show_id,seat_id=seat_id); db.add(seat)
        seat.status='HOLD'; seat.sales_version=config.sales_version; seat.reservation_id=reservation.id; seat.hold_by_user_id=user_id; seat.hold_expired_at=reservation.expires_at; seat.version+=1; seat.updated_at=now()
    db.commit()
    return [dict(seat_id=i,seat_name=seats[i]['seat_name'],status='HOLD',hold_expired_at=reservation.expires_at,reservation_id=reservation.id) for i in ids]

def release(db,show_id,seat_ids,user_id,reservation_id=None,*,cancel_all=False):
    gate(db,show_id,lock=True); expire_show(db,show_id)
    reservation=db.exec(select(Reservation).where(Reservation.showtime_id==show_id,Reservation.user_id==user_id,Reservation.status.in_(['ACTIVE','CHECKOUT'])).with_for_update()).first()
    if reservation is None: db.commit(); return 0
    if reservation_id and reservation.id!=reservation_id: raise HTTPException(409,'Reservation đã bị thay thế')
    if reservation.status=='CHECKOUT': raise HTTPException(409,'Đơn đang checkout; cần hủy đơn trước')
    ids=reservation.seat_ids if cancel_all else sorted(set(seat_ids))
    count=0
    for seat in rows(db,show_id,ids):
        if seat.reservation_id==reservation.id and seat.status=='HOLD':
            seat.status='AVAILABLE'; seat.hold_expired_at=None; seat.hold_by_user_id=None; seat.version+=1; count+=1
    reservation.seat_ids=sorted(set(reservation.seat_ids)-set(ids))
    if not reservation.seat_ids: reservation.status='RELEASED'
    db.commit(); return count

def availability(db,show_id,user_id=None):
    config=configuration(db,show_id); control=gate(db,show_id)
    current={r.seat_id:r for r in db.exec(select(SeatStatus).where(SeatStatus.showtime_id==show_id))}
    result=[]; stamp=now()
    can_sell=control.is_open and config.status=='ACTIVE' and datetime.combine(config.show_date,config.start_time)>datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).replace(tzinfo=None)
    for seat in config.snapshot['seats']:
        status='AVAILABLE' if can_sell and seat['status']=='ACTIVE' else 'UNAVAILABLE'
        row=current.get(seat['id']); deadline=None; mine=False
        if row and row.status=='BOOKED': status='BOOKED'
        elif row and row.status=='HOLD' and row.hold_expired_at>stamp:
            status='HOLD'; deadline=row.hold_expired_at; mine=row.hold_by_user_id==user_id
        result.append(dict(seat_id=seat['id'],seat_name=seat['seat_name'],seat_type=seat['seat_type'],price=float(seat['price']),status=status,hold_expired_at=deadline,is_held_by_me=mine,reservation_id=row.reservation_id if mine else None))
    return result
