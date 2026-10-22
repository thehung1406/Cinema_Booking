"""Read models for administration; aggregates never join payment attempts into sums."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_
from sqlmodel import select

from app.models import (Booking, BookingDetail, CinemaRoom, Film,
    Payment, Review, ReviewSentiment, Role, Seat, SeatStatus, Showtime, Ticket, User)


def page(db, statement, offset=0, limit=50):
    total = db.exec(select(func.count()).select_from(statement.order_by(None).subquery())).one()
    return {"items": db.exec(statement.offset(offset).limit(limit)).all(), "total": total}


def films(db, query, offset, limit):
    stmt = select(Film).where(Film.deleted_at.is_(None))
    if query:
        stmt = stmt.where(Film.title.icontains(query, autoescape=True))
    return page(db, stmt.order_by(Film.id.desc()), offset, limit)


def employees(db, query, offset, limit):
    stmt = select(User).join(Role, Role.id == User.role_id)
    if query:
        stmt = stmt.where(or_(User.username.icontains(query, autoescape=True),
            User.full_name.icontains(query, autoescape=True), User.email.icontains(query, autoescape=True)))
    # Include customers so an existing account can be promoted without creating a duplicate.
    result = page(db, stmt.order_by(User.id.desc()), offset, limit)
    result["items"] = [dict(id=u.id, username=u.username, full_name=u.full_name,
        email=u.email, phone=u.phone, role_id=u.role_id, role=u.role,
        is_active=u.is_active) for u in result["items"]]
    return result


def report(db, filters):
    """Sales/occupancy by show date in Vietnam; sentiments by last edit in that window."""
    from app.models.ai import utcnow
    show_conditions = [Showtime.show_date >= filters.start_date,
        Showtime.show_date <= filters.end_date, Showtime.status != "CANCELLED"]
    if filters.film_id:
        show_conditions.append(Showtime.film_id == filters.film_id)
    if filters.theater_id:
        show_conditions.append(CinemaRoom.theater_id == filters.theater_id)

    paid_attempt = select(Payment.id).where(Payment.booking_id == Booking.id,
        Payment.status == "PAID", Payment.amount == Booking.total_amount).exists()
    paid = [Booking.payment_status == "PAID", Booking.booking_status == "CONFIRMED", paid_attempt]
    eligible = (select(Booking.id).join(Showtime, Showtime.id == Booking.showtime_id)
        .join(CinemaRoom, CinemaRoom.id == Showtime.room_id).where(*show_conditions, *paid))
    revenue, booking_count = db.exec(select(func.coalesce(func.sum(Booking.total_amount), 0),
        func.count()).where(Booking.id.in_(eligible))).one()
    ticket_stmt = (select(func.count(Ticket.id)).join(BookingDetail,
        Ticket.booking_detail_id == BookingDetail.id).where(
        BookingDetail.booking_id.in_(eligible), Ticket.status.in_(["ISSUED", "USED"])))
    ticket_count = db.exec(ticket_stmt).one()
    seat_slots = db.exec(select(func.count(Seat.id)).join(Showtime, Showtime.room_id == Seat.room_id)
        .join(CinemaRoom, CinemaRoom.id == Showtime.room_id)
        .where(*show_conditions, Seat.status == "ACTIVE")).one()
    valid_ticket = (select(Ticket.id).join(BookingDetail, Ticket.booking_detail_id == BookingDetail.id)
        .join(Booking, Booking.id == BookingDetail.booking_id).where(
            BookingDetail.seat_id == SeatStatus.seat_id, Booking.showtime_id == SeatStatus.showtime_id,
            Booking.id.in_(eligible), Ticket.status.in_(["ISSUED", "USED"])).exists())
    occupied = db.exec(select(func.count(SeatStatus.id)).join(Showtime, Showtime.id == SeatStatus.showtime_id)
        .join(CinemaRoom, CinemaRoom.id == Showtime.room_id).join(Seat, Seat.id == SeatStatus.seat_id)
        .where(*show_conditions, Seat.status == "ACTIVE", SeatStatus.status == "BOOKED", valid_ticket)).one()
    sales = db.exec(select(Film.id, Film.title, func.sum(Booking.total_amount), func.count(Booking.id))
        .join(Showtime, Showtime.film_id == Film.id).join(Booking, Booking.showtime_id == Showtime.id)
        .where(Booking.id.in_(eligible)).group_by(Film.id, Film.title).order_by(Film.title)).all()
    ticket_rows = db.exec(select(Showtime.film_id, func.count(Ticket.id))
        .join(Booking, Booking.showtime_id == Showtime.id)
        .join(BookingDetail, BookingDetail.booking_id == Booking.id)
        .join(Ticket, Ticket.booking_detail_id == BookingDetail.id)
        .where(Booking.id.in_(eligible), Ticket.status.in_(["ISSUED", "USED"]))
        .group_by(Showtime.film_id)).all()
    tickets_by_film = dict(ticket_rows)

    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    begin = datetime.combine(filters.start_date, time.min, tzinfo=tz)
    end = datetime.combine(filters.end_date + timedelta(days=1), time.min, tzinfo=tz)
    review_conditions = [Review.is_deleted == False, Review.moderation_status == "approved",
        Review.updated_at >= begin, Review.updated_at < end, Review.updated_at <= utcnow()]
    if filters.film_id:
        review_conditions.append(Review.film_id == filters.film_id)
    if filters.theater_id:
        # Reviews belong to films, not theaters: constrain to films screened at that theater.
        review_conditions.append(Review.film_id.in_(select(Showtime.film_id)
            .join(CinemaRoom, CinemaRoom.id == Showtime.room_id).where(*show_conditions)))
    review_total = db.exec(select(func.count(Review.id)).where(*review_conditions)).one()
    sentiments = dict(positive=0, neutral=0, negative=0)
    rows = db.exec(select(ReviewSentiment.label, func.count(Review.id))
        .join(Review, Review.id == ReviewSentiment.review_id).where(*review_conditions,
            ReviewSentiment.content_version == Review.content_version,
            ReviewSentiment.status == "succeeded", ReviewSentiment.label.in_(list(sentiments)))
        .group_by(ReviewSentiment.label)).all()
    sentiments.update(dict(rows))
    analyzed = sum(sentiments.values())
    return dict(revenue=revenue, booking_count=booking_count, ticket_count=ticket_count,
        seat_slots=seat_slots, occupied_seats=occupied,
        occupancy=round(100 * occupied / seat_slots, 2) if seat_slots else 0,
        sentiments={**sentiments, "total": review_total, "pending": review_total-analyzed,
            "coverage": round(100 * analyzed / review_total, 2) if review_total else 0},
        by_film=[dict(film_id=i, title=t, revenue=r, bookings=n, tickets=tickets_by_film.get(i, 0))
            for i, t, r, n in sales], as_of=utcnow(), filters=filters.model_dump())
