"""Temporary reporting adapter using local Booking publications, never Cinema tables."""
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy import select, and_, or_, func
from app.models import Booking, BookingDetail, Payment, Ticket, SeatStatus, Review, ReviewSentiment
from app.models.sales import SalesConfiguration as Config, SalesGate
from app.services.sales_service import current_query


def report(db,filters):
    from app.models.ai import utcnow
    from app.utils.review_ownership import get_owner as review_owner
    from app.services.catalog_remote import film_batch
    conditions=[Config.show_date>=filters.start_date,Config.show_date<=filters.end_date,Config.status!="CANCELLED"]
    if filters.film_id: conditions.append(Config.film_id==filters.film_id)
    if filters.theater_id: conditions.append(Config.theater_id==filters.theater_id)
    paid_attempt=select(Payment.id).where(Payment.booking_id==Booking.id,Payment.status=="PAID",Payment.amount==Booking.total_amount).exists()
    rows=db.execute(select(Booking,Config).join(Config,and_(Config.showtime_id==Booking.showtime_id,Config.sales_version==Booking.sales_version))
        .where(*conditions,Booking.payment_status=="PAID",Booking.booking_status=="CONFIRMED",paid_attempt)).all()
    eligible=[b.id for b,c in rows]
    revenue=sum((b.total_amount for b,c in rows),Decimal("0"))
    tickets=db.execute(select(Ticket,BookingDetail).join(BookingDetail,BookingDetail.id==Ticket.booking_detail_id)
        .where(BookingDetail.booking_id.in_(eligible),Ticket.status.in_(["ISSUED","USED"]))).all()
    current=db.scalars(current_query().where(*conditions)).all()
    active={(c.showtime_id,s["id"]) for c in current for s in c.snapshot["seats"] if s["status"]=="ACTIVE"}
    booked=set(db.execute(select(SeatStatus.showtime_id,SeatStatus.seat_id).where(SeatStatus.status=="BOOKED")).all())
    by_booking={b.id:(b,c) for b,c in rows}
    occupied={(by_booking[d.booking_id][0].showtime_id,d.seat_id) for t,d in tickets} & active & booked
    sales={}
    for b,c in rows:
        item=sales.setdefault(c.film_id,{"revenue":Decimal("0"),"bookings":0,"tickets":0})
        item["revenue"]+=b.total_amount; item["bookings"]+=1
    for t,d in tickets: sales[by_booking[d.booking_id][1].film_id]["tickets"]+=1
    from app.utils.catalog_ownership import get_owner as catalog_owner
    if catalog_owner(db)=="service": facts=film_batch(sales.keys(),include_retired=True)
    elif catalog_owner(db)=="monolith":
        from app.models import Film
        facts={f.id:f for f in db.scalars(select(Film).where(Film.id.in_(list(sales))))}
    else:
        from fastapi import HTTPException
        raise HTTPException(503,"Catalog đang chuyển dữ liệu")
    if set(facts)!=set(sales):
        from fastapi import HTTPException
        raise HTTPException(503,"Thiếu nhãn phim hiện hành trong báo cáo")
    owner=review_owner(db)
    film_ids=[filters.film_id] if filters.film_id else None
    if filters.theater_id: film_ids=sorted({c.film_id for c in current})
    if owner=="service":
        from app.services.review_remote import report as remote
        db.rollback(); sentiment=remote(filters.start_date,filters.end_date,film_ids)
    elif owner=="maintenance":
        from fastapi import HTTPException
        raise HTTPException(503,"Review đang chuyển dữ liệu")
    else:
        begin=datetime.combine(filters.start_date,time.min,tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        end=datetime.combine(filters.end_date+timedelta(days=1),time.min,tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        criteria=[Review.is_deleted==False,Review.moderation_status=="approved",Review.updated_at>=begin,Review.updated_at<end,Review.updated_at<=utcnow()]
        if film_ids is not None: criteria.append(Review.film_id.in_(film_ids))
        total=db.scalar(select(func.count()).select_from(Review).where(*criteria))
        labels=dict(positive=0,neutral=0,negative=0)
        labels.update(dict(db.execute(select(ReviewSentiment.label,func.count()).join(Review,Review.id==ReviewSentiment.review_id)
            .where(*criteria,ReviewSentiment.status=="succeeded",ReviewSentiment.content_version==Review.content_version,
                ReviewSentiment.label.in_(list(labels))).group_by(ReviewSentiment.label)).all()))
        count=sum(labels.values()); sentiment={**labels,"total":total,"pending":total-count,"coverage":round(100*count/total,2) if total else 0}
    return dict(revenue=revenue,booking_count=len(rows),ticket_count=len(tickets),seat_slots=len(active),occupied_seats=len(occupied),
        occupancy=round(100*len(occupied)/len(active),2) if active else 0,sentiments=sentiment,
        by_film=[dict(film_id=i,title=facts[i].title,**sales[i]) for i in sorted(sales)],as_of=utcnow(),filters=filters.model_dump())
