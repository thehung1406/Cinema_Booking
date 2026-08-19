from typing import List, Optional
from sqlmodel import Session, select
from sqlalchemy import func
from app.models.booking import Booking
from app.models.booking_detail import BookingDetail
from app.models.seat_status import SeatStatus
from app.models.showtime import Showtime
from app.models.film import Film
from app.models.cinema_room import CinemaRoom
from app.models.theater import Theater
from app.models.seat import Seat
from app.models.seat_type import SeatType
from app.models.user import User


class BookingRepository:
    """Repository xử lý các thao tác database với Booking"""
    
    @staticmethod
    def create_booking(db: Session, booking_data: dict) -> Booking:
        """Tạo booking mới"""
        booking = Booking(**booking_data)
        db.add(booking)
        db.flush()  # Để lấy booking.id ngay
        db.refresh(booking)
        return booking
    
    @staticmethod
    def create_booking_details(db: Session, booking_id: int, seats: List[dict]) -> List[BookingDetail]:
        """Tạo chi tiết booking (ghế đã đặt)"""
        booking_details = []
        for seat in seats:
            detail = BookingDetail(
                booking_id=booking_id,
                seat_id=seat["seat_id"],
                price=seat["price"]
            )
            db.add(detail)
            booking_details.append(detail)
        db.flush()
        return booking_details
    
    @staticmethod
    def update_seat_status_to_booked(
        db: Session, 
        showtime_id: int, 
        seat_ids: List[int]
    ) -> None:
        """Cập nhật trạng thái ghế thành BOOKED trong database.
        Dùng WHERE IN thay vì loop từng ghế để giảm số lượng query.
        """
        if not seat_ids:
            return
        
        # Query 1 lần lấy tất cả seat_status cần update
        statement = select(SeatStatus).where(
            SeatStatus.showtime_id == showtime_id,
            SeatStatus.seat_id.in_(seat_ids)
        )
        existing_statuses = db.exec(statement).all()
        existing_seat_ids = {ss.seat_id for ss in existing_statuses}
        
        # Update các record đã tồn tại
        for seat_status in existing_statuses:
            seat_status.status = "BOOKED"
            seat_status.hold_by_user_id = None
            seat_status.hold_expired_at = None
        
        # Tạo mới cho các ghế chưa có seat_status
        new_seat_ids = set(seat_ids) - existing_seat_ids
        for seat_id in new_seat_ids:
            new_seat_status = SeatStatus(
                showtime_id=showtime_id,
                seat_id=seat_id,
                status="BOOKED"
            )
            db.add(new_seat_status)
    
    @staticmethod
    def get_booking_by_id(db: Session, booking_id: int) -> Optional[Booking]:
        """Lấy booking theo ID"""
        statement = select(Booking).where(Booking.id == booking_id)
        return db.exec(statement).first()
    
    @staticmethod
    def get_booking_with_details(db: Session, booking_id: int) -> Optional[dict]:
        """Lấy booking với đầy đủ thông tin chi tiết.
        Dùng JOIN để query 1 lần thay vì N+1 queries.
        """
        # Query 1: Lấy booking + user + showtime + film + room + theater bằng 1 JOIN
        statement = (
            select(
                Booking, User, Showtime, Film, CinemaRoom, Theater
            )
            .join(User, User.id == Booking.user_id)
            .join(Showtime, Showtime.id == Booking.showtime_id)
            .join(Film, Film.id == Showtime.film_id)
            .join(CinemaRoom, CinemaRoom.id == Showtime.room_id)
            .join(Theater, Theater.id == CinemaRoom.theater_id)
            .where(Booking.id == booking_id)
        )
        row = db.exec(statement).first()
        
        if not row:
            return None
        
        booking, user, showtime, film, room, theater = row
        
        # Query 2: Lấy tất cả booking_details + seat + seat_type bằng 1 JOIN
        seats_statement = (
            select(BookingDetail, Seat, SeatType)
            .join(Seat, Seat.id == BookingDetail.seat_id)
            .join(SeatType, SeatType.id == Seat.seat_type_id)
            .where(BookingDetail.booking_id == booking_id)
        )
        seat_rows = db.exec(seats_statement).all()
        
        seats_info = [
            {
                "seat_id": detail.seat_id,
                "seat_name": seat.seat_name,
                "seat_type": seat_type.name,
                "price": detail.price
            }
            for detail, seat, seat_type in seat_rows
        ]
        
        return {
            "id": booking.id,
            "bookingId": booking.id,
            "userId": booking.user_id,
            "showtimeId": booking.showtime_id,
            "bookingDate": booking.booking_date,
            "totalAmount": booking.total_amount,
            "paymentMethod": booking.payment_method,
            "paymentStatus": booking.payment_status,
            "bookingStatus": booking.booking_status,
            "filmTitle": film.title,
            "filmImage": film.image,
            "theaterName": theater.name,
            "roomName": room.name,
            "showDate": str(showtime.show_date),
            "startTime": str(showtime.start_time),
            "fullName": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "seats": seats_info
        }
    
    @staticmethod
    def get_bookings_by_user(db: Session, user_id: int) -> List[Booking]:
        """Lấy tất cả bookings của user"""
        statement = select(Booking).where(Booking.user_id == user_id).order_by(Booking.booking_date.desc())
        return db.exec(statement).all()
    
    @staticmethod
    def get_user_bookings_with_details(db: Session, user_id: int) -> List[dict]:
        """Lấy tất cả bookings của user với đầy đủ chi tiết.
        Dùng JOIN batch thay vì gọi get_booking_with_details trong loop.
        """
        # Query 1: Lấy tất cả bookings + related data bằng 1 JOIN
        statement = (
            select(
                Booking, User, Showtime, Film, CinemaRoom, Theater
            )
            .join(User, User.id == Booking.user_id)
            .join(Showtime, Showtime.id == Booking.showtime_id)
            .join(Film, Film.id == Showtime.film_id)
            .join(CinemaRoom, CinemaRoom.id == Showtime.room_id)
            .join(Theater, Theater.id == CinemaRoom.theater_id)
            .where(Booking.user_id == user_id)
            .order_by(Booking.booking_date.desc())
        )
        rows = db.exec(statement).all()
        
        if not rows:
            return []
        
        booking_ids = [row[0].id for row in rows]
        
        # Query 2: Lấy tất cả booking_details + seats + seat_types cho tất cả bookings
        seats_statement = (
            select(BookingDetail, Seat, SeatType)
            .join(Seat, Seat.id == BookingDetail.seat_id)
            .join(SeatType, SeatType.id == Seat.seat_type_id)
            .where(BookingDetail.booking_id.in_(booking_ids))
        )
        seat_rows = db.exec(seats_statement).all()
        
        # Group seats theo booking_id
        seats_by_booking = {}
        for detail, seat, seat_type in seat_rows:
            if detail.booking_id not in seats_by_booking:
                seats_by_booking[detail.booking_id] = []
            seats_by_booking[detail.booking_id].append({
                "seat_id": detail.seat_id,
                "seat_name": seat.seat_name,
                "seat_type": seat_type.name,
                "price": detail.price
            })
        
        # Build kết quả
        result = []
        for booking, user, showtime, film, room, theater in rows:
            result.append({
                "id": booking.id,
                "bookingId": booking.id,
                "userId": booking.user_id,
                "showtimeId": booking.showtime_id,
                "bookingDate": booking.booking_date,
                "totalAmount": booking.total_amount,
                "paymentMethod": booking.payment_method,
                "paymentStatus": booking.payment_status,
                "bookingStatus": booking.booking_status,
                "filmTitle": film.title,
                "filmImage": film.image,
                "theaterName": theater.name,
                "roomName": room.name,
                "showDate": str(showtime.show_date),
                "startTime": str(showtime.start_time),
                "fullName": user.full_name,
                "email": user.email,
                "phone": user.phone,
                "seats": seats_by_booking.get(booking.id, [])
            })
        
        return result
    
    @staticmethod
    def update_payment_status(db: Session, booking_id: int, payment_status: str) -> Optional[Booking]:
        """Cập nhật trạng thái thanh toán"""
        booking = BookingRepository.get_booking_by_id(db, booking_id)
        if booking:
            booking.payment_status = payment_status
            if payment_status == "PAID":
                booking.booking_status = "CONFIRMED"
            db.add(booking)
            db.flush()
            db.refresh(booking)
        return booking
