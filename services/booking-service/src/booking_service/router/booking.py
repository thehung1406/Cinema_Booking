from fastapi import APIRouter,Depends,Header,HTTPException,Query
from ..dependencies import get_session,get_current_user,require_staff
from ..schemas.booking import BookingCreateRequest,BookingDetailResponse
from ..booking_repo import BookingRepository
from .. import bookings

router=APIRouter(prefix='/bookings',tags=['Bookings'])

@router.post('',status_code=201)
def create(body:BookingCreateRequest,db=Depends(get_session),user=Depends(get_current_user),idempotency_key:str|None=Header(default=None)):
    return bookings.create(db,body,user.id,idempotency_key)

@router.get('',response_model=list[BookingDetailResponse])
def history(skip:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),db=Depends(get_session),user=Depends(get_current_user)):
    return BookingRepository.get_user_bookings_with_details(db,user.id,skip,limit)

@router.get('/{booking_id}',response_model=BookingDetailResponse)
def detail(booking_id:int,db=Depends(get_session),user=Depends(get_current_user)):
    booking=BookingRepository.get_booking_by_id(db,booking_id)
    if booking is None: raise HTTPException(404,'Booking không tồn tại')
    if booking.user_id!=user.id: raise HTTPException(403,'Bạn không có quyền xem đơn này')
    return BookingRepository.get_booking_with_details(db,booking_id)

@router.patch('/{booking_id}/payment-status',response_model=BookingDetailResponse)
def cancel(booking_id:int,payment_status:str=Query(pattern='^(FAILED|CANCELLED)$'),db=Depends(get_session),staff=Depends(require_staff)):
    return bookings.cancel(db,booking_id,payment_status)
