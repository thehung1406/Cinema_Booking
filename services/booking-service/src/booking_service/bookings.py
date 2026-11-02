from decimal import Decimal
import json
from uuid import UUID
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text
from sqlmodel import select
from .models import Booking,BookingDetail,Reservation,Idempotency
from .schemas.booking import BookingResponse,BookingDetailResponse
from .sales import configuration
from .reservations import now,rows,expire_show
from .food import FoodService
from .clients import contact
from .checkout import digest,create_checkout
from .booking_repo import BookingRepository

def create(db,request,user_id,key=None):
    if request.userId!=user_id: raise HTTPException(403,'Không thể đặt vé cho người dùng khác')
    ids=sorted(s.seat_id for s in request.seats)
    if len(ids)!=len(set(ids)) or not ids or len(ids)>20: raise HTTPException(400,'Danh sách ghế không hợp lệ')
    if key is not None and (not 1<=len(key)<=128 or any(ord(c)<33 or ord(c)>126 for c in key)): raise HTTPException(400,'Idempotency-Key không hợp lệ')
    # Acquire per-request lock before the show gate; no reverse acquisition exists.
    if key: db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,2))'),{'key':str(user_id)+':'+key})
    expected=dict(user_id=user_id,showtime_id=request.showtimeId,reservation_id=request.reservationId,
        seats=ids,food=sorted((s.food_item_id,s.quantity) for s in request.foodItems),amount=format(Decimal(str(request.totalAmount)),'.2f'),method=request.paymentMethod)
    request_hash=digest(expected)
    if key:
        old=db.get(Idempotency,(user_id,key))
        if old:
            if old.request_hash!=request_hash: raise HTTPException(409,'Idempotency-Key đã dùng cho yêu cầu khác')
            return old.response
    config=configuration(db,request.showtimeId,lock=True)
    # Before expiry, resolve replay by reservation even when the order is now paid/expired.
    reservation=None
    if request.reservationId:
        reservation=db.get(Reservation,request.reservationId)
        if reservation is None or reservation.user_id!=user_id or reservation.showtime_id!=request.showtimeId: raise HTTPException(409,'Sai reservation')
    else:
        reservation=db.exec(select(Reservation).where(Reservation.user_id==user_id,Reservation.showtime_id==request.showtimeId,Reservation.status.in_(['ACTIVE','CHECKOUT'])).with_for_update()).first()
    if reservation is None: raise HTTPException(409,'Không có reservation đang giữ')
    replay_key=key or 'reservation:'+reservation.id
    old=db.get(Idempotency,(user_id,replay_key))
    if old:
        if old.request_hash!=request_hash: raise HTTPException(409,'Reservation đã checkout với nội dung khác')
        return old.response
    previous=db.exec(select(Booking.id).where(Booking.reservation_id==reservation.id)).first()
    if previous: raise HTTPException(409,'Reservation đã có đơn; dùng lại Idempotency-Key của yêu cầu trước')
    expire_show(db,request.showtimeId)
    if reservation.status!='ACTIVE' or reservation.expires_at<=now() or reservation.sales_version!=config.sales_version or reservation.seat_ids!=ids: raise HTTPException(409,'Reservation hết hạn, đã checkout hoặc danh sách ghế không khớp')
    held=rows(db,request.showtimeId,ids)
    if len(held)!=len(ids) or any(s.status!='HOLD' or s.reservation_id!=reservation.id or s.hold_by_user_id!=user_id or s.hold_expired_at<=now() or s.sales_version!=config.sales_version for s in held): raise HTTPException(409,'Ghế không còn được giữ bởi reservation này')
    seats={s['id']:s for s in config.snapshot['seats']}
    lines,total=FoodService.quote(db,request.foodItems)
    ticket_lines=[dict(seat_id=i,price=Decimal(seats[i]['price'])) for i in ids]
    total+=sum((s['price'] for s in ticket_lines),Decimal('0'))
    if total<=0 or total>=Decimal('10000000000') or total!=Decimal(str(request.totalAmount)): raise HTTPException(400,'Tổng tiền không khớp giá server')
    customer=contact(user_id)
    # Check wall time again after dependent calls; deadline is never extended.
    if reservation.expires_at<=now(): raise HTTPException(409,'Reservation đã hết hạn trong lúc checkout')
    booking=Booking(user_id=user_id,showtime_id=request.showtimeId,reservation_id=reservation.id,sales_version=config.sales_version,
        catalog_film_snapshot=config.snapshot['film'],total_amount=total,payment_method=request.paymentMethod,expires_at=reservation.expires_at,
        customer_full_name=customer.full_name,customer_email=customer.email,customer_phone=customer.phone)
    db.add(booking); db.flush()
    for seat in ticket_lines: db.add(BookingDetail(booking_id=booking.id,**seat))
    db.flush(); FoodService.save(db,booking.id,lines)
    reservation.status='CHECKOUT'; db.flush()
    create_checkout(db,booking)
    from .events import checkout_event
    checkout_event(db,booking,"CheckoutCreated.v1")
    response=BookingResponse(bookingId=booking.id,userId=user_id,showtimeId=booking.showtime_id,bookingDate=booking.booking_date,
        totalAmount=booking.total_amount,paymentMethod=booking.payment_method,paymentStatus=booking.payment_status,bookingStatus=booking.booking_status,
        seats=ticket_lines,foodItems=FoodService.for_bookings(db,[booking.id]).get(booking.id,[])).model_dump(mode='json')
    response.update(reservationId=reservation.id,bookingVersion=1,expiresAt=booking.expires_at.isoformat())
    db.add(Idempotency(user_id=user_id,key=replay_key,request_hash=request_hash,booking_id=booking.id,response=response))
    db.commit(); return response

def cancel(db,booking_id,status):
    booking=BookingRepository.get_booking_by_id(db,booking_id,for_update=True)
    if booking is None: raise HTTPException(404,'Booking không tồn tại')
    if booking.payment_status=='PAID': raise HTTPException(409,'Không thể hủy đơn đã thanh toán')
    from .payments import release_booking
    booking.booking_status='CANCELLED'; booking.payment_status=status
    release_booking(db,booking,'RELEASED'); db.commit()
    return BookingRepository.get_booking_with_details(db,booking.id)
