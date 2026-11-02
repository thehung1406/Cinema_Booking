from datetime import date, datetime, time, timezone
from decimal import Decimal
from sqlalchemy import (Column, DateTime, ForeignKey, ForeignKeyConstraint, Integer, JSON, Numeric,
    String, UniqueConstraint, CheckConstraint, Index, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow(): return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Theater(Base):
    __tablename__ = "theaters"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(50))
    image: Mapped[str | None] = mapped_column(String(255))
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3,1))
    technologies: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    special: Mapped[str | None] = mapped_column(String(50))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CinemaRoom(Base):
    __tablename__ = "cinema_rooms"
    __table_args__ = (CheckConstraint("capacity BETWEEN 1 AND 2000", name="ck_room_capacity"),
        Index("uq_live_room_theater_name", "theater_id", "name", unique=True, postgresql_where=text("deleted_at IS NULL")))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    theater_id: Mapped[int] = mapped_column(ForeignKey("theaters.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(50))
    capacity: Mapped[int]
    room_type: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    operation_id: Mapped[str | None] = mapped_column(String(36))


class SeatType(Base):
    __tablename__ = "seat_types"
    __table_args__ = (UniqueConstraint("room_id", "name", name="uq_seat_type_room_name"),
        UniqueConstraint("room_id", "id", name="uq_seat_type_room_id"),
        CheckConstraint("base_price >= 0", name="ck_seat_type_price"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("cinema_rooms.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(30))
    base_price: Mapped[Decimal] = mapped_column(Numeric(12,2))


class Seat(Base):
    __tablename__ = "seats"
    __table_args__ = (ForeignKeyConstraint(["room_id", "seat_type_id"], ["seat_types.room_id", "seat_types.id"], ondelete="RESTRICT"),
        Index("uq_seat_room_name", "room_id", "seat_name", unique=True, postgresql_where=text("deleted_at IS NULL")))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("cinema_rooms.id", ondelete="RESTRICT"), index=True)
    seat_type_id: Mapped[int] = mapped_column(Integer, index=True)
    seat_name: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Showtime(Base):
    __tablename__ = "showtimes"
    __table_args__ = (CheckConstraint("end_time > start_time", name="ck_showtime_interval"),
        Index("ix_showtimes_film_date_status", "film_id", "show_date", "status"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    film_id: Mapped[int] = mapped_column(Integer, index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("cinema_rooms.id", ondelete="RESTRICT"), index=True)
    format_id: Mapped[int] = mapped_column(Integer, index=True)
    show_date: Mapped[date]
    start_time: Mapped[time]
    end_time: Mapped[time]
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")
    catalog_binding_id: Mapped[str | None] = mapped_column(String(36))
    catalog_film_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    sales_version: Mapped[int] = mapped_column(default=0, server_default="0")
    control_epoch: Mapped[int] = mapped_column(default=0, server_default="0")
    sales_state: Mapped[str] = mapped_column(String(30), default="CLOSED", server_default="CLOSED")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def format(self): return self.catalog_film_snapshot.get("format_name", "")


class Publication(Base):
    __tablename__ = "sales_publications"
    showtime_id: Mapped[int] = mapped_column(ForeignKey("showtimes.id", ondelete="RESTRICT"), primary_key=True)
    sales_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    digest: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
    acknowledged: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Operation(Base):
    __tablename__ = "cinema_operations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("cinema_rooms.id", ondelete="RESTRICT"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    progress: Mapped[dict] = mapped_column(JSON, default=dict)
    phase: Mapped[str] = mapped_column(String(30), default="CLOSING")
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    message: Mapped[str] = mapped_column(String(500), default="Đang đóng nhận giữ ghế mới")
    result: Mapped[dict | None] = mapped_column(JSON)
    actor_id: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
