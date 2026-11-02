from datetime import date
from decimal import Decimal
from sqlalchemy import select,and_
from .models import Booking,BookingDetail,Payment,Ticket,SeatStatus,SalesConfiguration as Config
from .sales import current_query,future_query
from .reservations import availability

def report(db,start_date,end_date,film_id=None,theater_id=None):
    criteria=[Config.show_date>=start_date,Config.show_date<=end_date,Config.status!='CANCELLED']
    if film_id: criteria.append(Config.film_id==film_id)
    if theater_id: criteria.append(Config.theater_id==theater_id)
    from .payment_ownership import owner
    from .models.payment_saga import PaymentReceipt
    active=owner(db)
    if active=='maintenance':
        from fastapi import HTTPException
        raise HTTPException(503,'Payment đang chuyển dữ liệu')
    paid=(select(PaymentReceipt.payment_id).where(PaymentReceipt.booking_id==Booking.id,PaymentReceipt.outcome=='CONFIRMED',PaymentReceipt.amount==Booking.total_amount).exists()) if active=='service' else select(Payment.id).where(Payment.booking_id==Booking.id,Payment.status=='PAID',Payment.amount==Booking.total_amount).exists()
    orders=db.execute(select(Booking,Config).join(Config,and_(Config.showtime_id==Booking.showtime_id,Config.sales_version==Booking.sales_version)).where(*criteria,Booking.payment_status=='PAID',Booking.booking_status=='CONFIRMED',paid)).all()
    by_booking={b.id:(b,c) for b,c in orders}
    tickets=db.execute(select(Ticket,BookingDetail).join(BookingDetail,BookingDetail.id==Ticket.booking_detail_id).where(BookingDetail.booking_id.in_(by_booking),Ticket.status.in_(['ISSUED','USED']))).all()
    configs=list(db.scalars(current_query().where(*criteria)))
    slots={(c.showtime_id,s['id']) for c in configs for s in c.snapshot['seats'] if s['status']=='ACTIVE'}
    booked=set(db.execute(select(SeatStatus.showtime_id,SeatStatus.seat_id).where(SeatStatus.status=='BOOKED')).all())
    occupied={(by_booking[d.booking_id][0].showtime_id,d.seat_id) for t,d in tickets}&slots&booked
    sales={}
    for b,c in orders:
        item=sales.setdefault(c.film_id,dict(film_id=c.film_id,revenue=Decimal('0'),bookings=0,tickets=0))
        item['revenue']+=b.total_amount; item['bookings']+=1
    for t,d in tickets: sales[by_booking[d.booking_id][1].film_id]['tickets']+=1
    return dict(revenue=sum((b.total_amount for b,c in orders),Decimal('0')),booking_count=len(orders),ticket_count=len(tickets),seat_slots=len(slots),occupied_seats=len(occupied),occupancy=round(100*len(occupied)/len(slots),2) if slots else 0,by_film=[sales[i] for i in sorted(sales)],screened_film_ids=sorted({c.film_id for c in configs}))

def verified(db,items):
    result=[]
    for item in items:
        found=db.scalar(select(Booking.id).join(Config,and_(Config.showtime_id==Booking.showtime_id,Config.sales_version==Booking.sales_version)).where(Booking.user_id==item['user_id'],Config.film_id==item['film_id'],Booking.payment_status=='PAID',Booking.booking_status=='CONFIRMED').limit(1))
        result.append({**item,'verified_purchase':found is not None})
    return result

def tool(db,call,evening=False):
    from fastapi import HTTPException
    from .sales import configuration
    name=call.get('name'); context=call.get('context') or {}
    if name=='get_showtimes':
        if not all(context.get(k) for k in ('film_id','theater_id','show_date')): raise HTTPException(422,'Thiếu tham số công cụ')
        shows=db.scalars(future_query(context['film_id'],context['theater_id'],date.fromisoformat(context['show_date']),evening).limit(20)).all()
        return [dict(id=f'showtime:{s.id}',title=f'Suất {s.start_time:%H:%M}',text=f'{s.show_date:%d/%m/%Y}, {s.start_time:%H:%M}, định dạng {s.format}, mã suất {s.id}.',url=f'/seat-selection/{s.id}',kind='live') for s in shows]
    if name not in {'get_ticket_prices','get_seat_availability'} or not context.get('showtime_id'): raise HTTPException(422,'Công cụ không được phép hoặc thiếu tham số')
    show=db.scalars(future_query().where(Config.showtime_id==context['showtime_id'])).first()
    if show is None: return []
    url=f'/seat-selection/{show.id}'
    if name=='get_ticket_prices':
        prices={s['seat_type_id']:s for s in show.snapshot['seats'] if s['status']=='ACTIVE'}
        return [dict(id=f'price:{i}',title=p['seat_type'],text=f"Suất {show.id}, ghế {p['seat_type']}: {Decimal(p['price']):,.0f} VND.",url=url,kind='live') for i,p in sorted(prices.items())]
    seats=availability(db,show.id)
    count=sum(s['status']=='AVAILABLE' for s in seats)
    return [dict(id=f'seats:{show.id}',title='Ghế trống',text=f'Suất {show.id}: {count}/{len(seats)} ghế đang trống. Cần kiểm tra lại khi chọn ghế.',url=url,kind='live')]
