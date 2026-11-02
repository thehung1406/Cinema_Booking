from datetime import datetime,timezone
from decimal import Decimal
import logging
from fastapi import HTTPException
from sqlmodel import select
from .config import settings
from .models import Booking,BookingDetail,Payment,Reservation
from .booking_repo import BookingRepository
from .payment_repo import PaymentRepository
from .checkout import require_checkout
from .reservations import rows,now
from .tickets import TicketService
from .events import booking_confirmed

log=logging.getLogger('booking.payment')

def release_booking(db,booking,reservation_status):
    reservation=db.get(Reservation,booking.reservation_id)
    if reservation:
        for seat in rows(db,booking.showtime_id,reservation.seat_ids):
            if seat.status=='HOLD' and seat.reservation_id==reservation.id:
                seat.status='AVAILABLE'; seat.hold_by_user_id=None; seat.hold_expired_at=None; seat.version+=1
        if reservation.status!='CONFIRMED': reservation.status=reservation_status

class PaymentService:
    @staticmethod
    def resolve_booking_id(db,merchant_ref):
        payment=PaymentRepository.get_by_ref(db,merchant_ref)
        if payment is None or payment.provider!='VNPAY': raise HTTPException(404,'Giao dịch không tồn tại')
        return payment.booking_id

    @staticmethod
    def validate_vnpay_payment_params(booking,params,payment=None):
        if not params or payment is None: return 'Thiếu giao dịch'
        if str(params.get('vnp_TxnRef'))!=payment.merchant_ref or params.get('vnp_TmnCode')!=settings.tmn_code: return 'Merchant hoặc tham chiếu không khớp'
        try:
            if int(str(params.get('vnp_Amount')))!=int(booking.total_amount*100) or payment.amount!=booking.total_amount or payment.currency!=booking.currency: return 'Số tiền không khớp'
        except (ValueError,TypeError): return 'Số tiền không hợp lệ'
        return None

    @staticmethod
    def _apply(db,booking_id,params):
        booking=BookingRepository.get_booking_by_id(db,booking_id,for_update=True)
        if booking is None: raise HTTPException(404,'Booking không tồn tại')
        checkout=require_checkout(db,booking)
        payment=PaymentRepository.get_by_ref(db,params.get('vnp_TxnRef'),for_update=True)
        if payment is None or payment.booking_id!=booking.id or payment.provider!='VNPAY' or payment.checkout_version!=checkout.booking_version: raise HTTPException(400,'Giao dịch không thuộc checkout')
        error=PaymentService.validate_vnpay_payment_params(booking,params,payment)
        if error: raise HTTPException(400,error)
        success=params.get('vnp_ResponseCode')=='00' and params.get('vnp_TransactionStatus',params.get('vnp_ResponseCode'))=='00'
        PaymentRepository.record_result(db,payment,params,success)
        if booking.payment_status=='PAID': db.commit(); return booking,True,True
        if booking.booking_status in ('EXPIRED','CANCELLED') or booking.payment_status in ('FAILED','CANCELLED'):
            db.commit(); return booking,False,True
        if checkout.deadline<=now():
            booking.booking_status='EXPIRED'
            # Provider PAID remains on the attempt; Booking did not issue tickets.
            booking.payment_status='FAILED'
            release_booking(db,booking,'EXPIRED')
            from .events import checkout_event
            checkout_event(db,booking,"BookingExpired.v1")
            db.commit(); return booking,False,True
        reservation=db.get(Reservation,booking.reservation_id)
        if reservation is None or reservation.status!='CHECKOUT' or reservation.expires_at<=now(): raise HTTPException(409,'Reservation không thể xác nhận')
        if success:
            details=db.exec(select(BookingDetail).where(BookingDetail.booking_id==booking.id).order_by(BookingDetail.seat_id)).all()
            held=rows(db,booking.showtime_id,[d.seat_id for d in details])
            if len(held)!=len(details) or any(s.status!='HOLD' or s.reservation_id!=reservation.id or s.sales_version!=booking.sales_version or s.hold_by_user_id!=booking.user_id or s.hold_expired_at<=now() for s in held): raise HTTPException(409,'Hold đã hết hạn hoặc bị thay thế')
            for seat in held:
                seat.status='BOOKED'; seat.hold_by_user_id=None; seat.hold_expired_at=None; seat.version+=1; seat.updated_at=now()
            booking.payment_status='PAID'; booking.booking_status='CONFIRMED'; reservation.status='CONFIRMED'
            db.flush(); TicketService.issue_for_booking(db,booking)
            booking_confirmed(db,booking,payment.id)
        else:
            booking.payment_status='FAILED'; booking.booking_status='CANCELLED'; release_booking(db,booking,'RELEASED')
        db.commit(); return booking,success,False

    @staticmethod
    def preserve(db,booking_id,params):
        # Preserve validated provider evidence if the seat/ticket transaction rolls back.
        db.rollback()
        booking=BookingRepository.get_booking_by_id(db,booking_id,for_update=True)
        if booking is None: return
        payment=PaymentRepository.get_by_ref(db,params.get('vnp_TxnRef'),for_update=True)
        if payment is None or payment.booking_id!=booking_id or PaymentService.validate_vnpay_payment_params(booking,params,payment): return
        success=params.get('vnp_ResponseCode')=='00' and params.get('vnp_TransactionStatus',params.get('vnp_ResponseCode'))=='00'
        PaymentRepository.record_result(db,payment,params,success); db.commit()

    @staticmethod
    def confirm_vnpay_payment(db,booking_id,vnp_response_code,vnp_params=None):
        params=vnp_params or {}
        try:
            booking,success,repeated=PaymentService._apply(db,booking_id,params)
            return dict(status='success' if success else 'failed',booking=BookingRepository.get_booking_with_details(db,booking.id) if success else None,message='Thanh toán thành công' if success else 'Đơn đã hết hạn, bị hủy hoặc thanh toán thất bại')
        except HTTPException as exc:
            db.rollback()
            if exc.status_code in {404,400}: return dict(status='failed',booking=None,message=str(exc.detail))
            PaymentService.preserve(db,booking_id,params); raise
        except Exception as exc:
            db.rollback()
            try: PaymentService.preserve(db,booking_id,params)
            except Exception: db.rollback(); log.error('provider evidence deferred')
            raise HTTPException(503,'Chưa thể xác nhận đơn; giao dịch cần đối soát') from exc

    @staticmethod
    def process_vnpay_ipn(db,params):
        from .router.payment import verify_vnpay_signature
        if not verify_vnpay_signature(params): return dict(RspCode='97',Message='Invalid Checksum')
        try: booking_id=PaymentService.resolve_booking_id(db,params.get('vnp_TxnRef'))
        except HTTPException: return dict(RspCode='01',Message='Order Not Found')
        try:
            booking,success,repeated=PaymentService._apply(db,booking_id,params)
            return dict(RspCode='02' if repeated else '00',Message='Order already confirmed' if repeated else 'Confirm Success')
        except HTTPException as exc:
            db.rollback()
            if exc.status_code==400: return dict(RspCode='04' if 'Số tiền' in str(exc.detail) else '99',Message='Invalid payment data')
        except Exception: db.rollback()
        try: PaymentService.preserve(db,booking_id,params)
        except Exception: db.rollback(); log.error('provider evidence deferred')
        return dict(RspCode='99',Message='Unknown error')

    @staticmethod
    def get_payment_status(db,booking_id,user_id=None):
        booking=BookingRepository.get_booking_by_id(db,booking_id)
        if booking is None: raise HTTPException(404,'Booking không tồn tại')
        if booking.user_id!=user_id: raise HTTPException(403,'Bạn không có quyền xem đơn này')
        return dict(booking_id=booking.id,payment_status=booking.payment_status,booking_status=booking.booking_status,payment_method=booking.payment_method,total_amount=booking.total_amount,booking_date=booking.booking_date)
