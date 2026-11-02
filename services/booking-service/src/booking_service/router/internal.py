from datetime import date
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,Field
from ..dependencies import private,writes,get_session
from ..schemas.sales import SalesCommand,ImportSales,OpenSales
from .. import sales,facts

router=APIRouter(dependencies=[Depends(private)],include_in_schema=False)

@router.get('/internal/v1/migration/state')
def migration(request:Request): return dict(writes_enabled=request.app.state.settings.writes_enabled)

@router.post('/internal/v1/sales/{showtime_id}/close',dependencies=[Depends(writes)])
def close(showtime_id:int,body:SalesCommand,db=Depends(get_session)): return sales.close(db,showtime_id,body.epoch)

@router.post('/internal/v1/sales/{showtime_id}/import',dependencies=[Depends(writes)])
def install(showtime_id:int,body:ImportSales,db=Depends(get_session)):
    if showtime_id!=body.snapshot.showtime_id: raise HTTPException(409,'Sai suất công bố')
    return sales.install(db,body.snapshot,body.digest,body.epoch)

@router.post('/internal/v1/sales/{showtime_id}/open',dependencies=[Depends(writes)])
def open_sales(showtime_id:int,body:OpenSales,db=Depends(get_session)): return sales.open_sales(db,showtime_id,body.sales_version,body.digest,body.epoch)

@router.get('/internal/v1/sales/{showtime_id}/state')
def state(showtime_id:int,seat_id:int|None=None,db=Depends(get_session)):
    row=sales.gate(db,showtime_id,lock=True,create=True)
    result=dict(epoch=row.epoch,is_open=row.is_open,sales_version=row.sales_version,**sales.stats(db,showtime_id,seat_id=seat_id))
    db.commit(); return result

@router.get('/internal/v1/booking-read/report')
def report(start_date:date,end_date:date,film_id:int|None=None,theater_id:int|None=None,db=Depends(get_session)):
    if end_date<start_date: raise HTTPException(422,'Sai khoảng ngày')
    return facts.report(db,start_date,end_date,film_id,theater_id)

class Verification(BaseModel): items:list[dict]=Field(max_length=100)

@router.post('/internal/v1/booking-read/verified')
def verified(body:Verification,db=Depends(get_session)):
    if any(set(i)!={'user_id','film_id'} or not all(isinstance(v,int) and v>0 for v in i.values()) for i in body.items): raise HTTPException(422,'Sai danh sách xác minh')
    return facts.verified(db,body.items)

@router.get('/internal/v1/booking-read/candidates')
def candidates(theater_id:int|None=None,show_date:date|None=None,evening:bool=False,db=Depends(get_session)):
    from ..models import SalesConfiguration as Config
    query=sales.future_query(theater_id=theater_id,show_date=show_date,evening=evening).subquery()
    from sqlalchemy import select
    return list(db.scalars(select(query.c.film_id).distinct()))

class Context(BaseModel):
    film_id:int|None=Field(default=None,gt=0)
    theater_id:int|None=Field(default=None,gt=0)
    showtime_id:int|None=Field(default=None,gt=0)
    show_date:date|None=None

@router.post('/internal/v1/booking-read/context')
def context(body:Context,db=Depends(get_session)):
    if body.showtime_id:
        item=sales.configuration(db,body.showtime_id)
        if (body.film_id and item.film_id!=body.film_id) or (body.theater_id and item.theater_id!=body.theater_id) or (body.show_date and item.show_date!=body.show_date): raise HTTPException(422,'Suất không khớp ngữ cảnh')
    return dict(valid=True)

class Invocation(BaseModel):
    call:dict
    evening:bool=False

@router.post('/internal/v1/booking-read/tool')
def tool(body:Invocation,db=Depends(get_session)):
    context(Context.model_validate(body.call.get('context') or {}),db)
    return facts.tool(db,body.call,body.evening)

@router.get('/internal/v1/checkouts/{booking_id}')
def checkout(booking_id:int,db=Depends(get_session)):
    from ..booking_repo import BookingRepository
    from ..checkout import require_checkout
    booking=BookingRepository.get_booking_by_id(db,booking_id)
    if booking is None: raise HTTPException(404,'Không có checkout')
    item=require_checkout(db,booking)
    # Payment boundary does not require PII, film metadata or food descriptions.
    return dict(user_id=booking.user_id,payment_method=booking.payment_method,booking_date=booking.booking_date,booking_id=booking.id,booking_version=item.booking_version,reservation_id=item.reservation_id,amount=str(item.amount),currency=item.currency,deadline=item.deadline,digest=item.digest,booking_status=booking.booking_status,payment_status=booking.payment_status)

class Bridge(BaseModel): booking_id:int=Field(gt=0)

@router.post('/internal/v1/booking-read/legacy-email',dependencies=[Depends(writes)])
def legacy_email(body:Bridge,db=Depends(get_session)):
    from ..booking_repo import BookingRepository
    from ..events import booking_confirmed
    from cinema_platform.events import OutboxRecord
    from uuid import uuid5,NAMESPACE_URL
    booking=BookingRepository.get_booking_by_id(db,body.booking_id,for_update=True)
    if booking is None or booking.payment_status!='PAID' or booking.booking_status!='CONFIRMED': raise HTTPException(409,'Đơn chưa được xác nhận')
    event_id=str(uuid5(NAMESPACE_URL,f'cinema:booking:{booking.id}:BookingConfirmationEmailRequested.v1'))
    if db.get(OutboxRecord,event_id) is None: booking_confirmed(db,booking,None,include_public=False)
    db.commit(); return dict(migrated=True,sent=False)


@router.get('/internal/v1/payment-ownership')
def payment_ownership(db=Depends(get_session)):
    from ..payment_ownership import owner
    return dict(owner=owner(db))

@router.get('/internal/v1/payment-results/{payment_id}')
def payment_result(payment_id:int,db=Depends(get_session)):
    from ..models.payment_saga import PaymentReceipt
    row=db.get(PaymentReceipt,payment_id)
    if row is None: raise HTTPException(404,'Chưa có kết quả xác nhận')
    return row.result
