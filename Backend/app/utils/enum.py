from enum import Enum


class UserRole(str, Enum):
    STAFF = "STAFF"
    USER = "USER"
    ADMIN = "ADMIN"

class SeatStatusEnum(str, Enum):
    AVAILABLE = "AVAILABLE"
    HOLD = "HOLD"
    BOOKED = "BOOKED"

class BookingStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
