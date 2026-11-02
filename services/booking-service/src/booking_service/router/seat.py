from fastapi import APIRouter,Depends
from ..dependencies import get_session,get_current_user,get_optional_current_user
from ..schemas.seat import HoldSeatRequest,ReleaseSeatRequest,SeatStatusResponse,HoldSeatResponse
from .. import reservations

router=APIRouter(prefix='/seats',tags=['Seats'])

@router.get('/showtime/{showtime_id}',response_model=list[SeatStatusResponse])
def availability(showtime_id:int,db=Depends(get_session),user=Depends(get_optional_current_user)):
    return reservations.availability(db,showtime_id,user.id if user else None)

@router.get('/showtime/{showtime_id}/available-count')
def count(showtime_id:int,db=Depends(get_session)):
    return dict(showtime_id=showtime_id,available_seats=sum(s['status']=='AVAILABLE' for s in reservations.availability(db,showtime_id)))

@router.post('/hold',response_model=list[HoldSeatResponse])
def hold(body:HoldSeatRequest,db=Depends(get_session),user=Depends(get_current_user)):
    return reservations.hold(db,body.showtime_id,body.seat_ids,user.id,body.reservation_id)

@router.post('/release')
def release(body:ReleaseSeatRequest,db=Depends(get_session),user=Depends(get_current_user)):
    count=reservations.release(db,body.showtime_id,body.seat_ids,user.id,body.reservation_id)
    return dict(released_seats=count,message=f'Đã hủy giữ {count} ghế')

@router.delete('/showtime/{showtime_id}/cancel-hold')
def cancel(showtime_id:int,db=Depends(get_session),user=Depends(get_current_user)):
    count=reservations.release(db,showtime_id,[],user.id,cancel_all=True)
    return dict(showtime_id=showtime_id,cancelled_seats=count,message=f'Đã hủy {count} ghế')
