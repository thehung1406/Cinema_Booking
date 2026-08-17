"""Optimize: composite indexes, Numeric for money, ON DELETE CASCADE

Revision ID: 002
Revises: 001
Create Date: 2026-08-17 15:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, Sequence[str], None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Tối ưu database: indexes, kiểu dữ liệu tiền, cascade."""

    # ──────────────────────────────────────────
    # 1. Composite indexes cho các query phổ biến
    # ──────────────────────────────────────────

    # Showtime: query theo (film_id, show_date, status)
    op.create_index(
        "ix_showtimes_film_date_status",
        "showtimes",
        ["film_id", "show_date", "status"],
    )

    # SeatStatus: query theo (showtime_id, status) — đếm ghế trống
    op.create_index(
        "ix_seat_status_showtime_status",
        "seat_status",
        ["showtime_id", "status"],
    )

    # Film: query phim đang chiếu theo (release_date, end_date)
    op.create_index(
        "ix_films_release_end_date",
        "films",
        ["release_date", "end_date"],
    )

    # Booking: query theo (user_id, booking_date DESC) — lịch sử booking
    op.create_index(
        "ix_bookings_user_date",
        "bookings",
        ["user_id", sa.text("booking_date DESC")],
    )

    # SeatStatus: index trên hold_expired_at cho cleanup job
    op.create_index(
        "ix_seat_status_hold_expired",
        "seat_status",
        ["hold_expired_at"],
        postgresql_where=sa.text("status = 'HOLD' AND hold_expired_at IS NOT NULL"),
    )

    # ──────────────────────────────────────────
    # 2. float → Numeric(12,2) cho các cột tiền tệ
    # ──────────────────────────────────────────

    # seats.price
    op.alter_column(
        "seats", "price",
        type_=sa.Numeric(12, 2),
        existing_type=sa.Float(),
        existing_nullable=False,
        postgresql_using="price::numeric(12,2)"
    )

    # booking_details.price
    op.alter_column(
        "booking_details", "price",
        type_=sa.Numeric(12, 2),
        existing_type=sa.Float(),
        existing_nullable=False,
        postgresql_using="price::numeric(12,2)"
    )

    # bookings.total_amount
    op.alter_column(
        "bookings", "total_amount",
        type_=sa.Numeric(12, 2),
        existing_type=sa.Float(),
        existing_nullable=False,
        postgresql_using="total_amount::numeric(12,2)"
    )

    # theaters.rating → Numeric(3,1) cho rating
    op.alter_column(
        "theaters", "rating",
        type_=sa.Numeric(3, 1),
        existing_type=sa.Float(),
        existing_nullable=True,
        postgresql_using="rating::numeric(3,1)"
    )

    # ──────────────────────────────────────────
    # 3. ON DELETE CASCADE trên FK quan trọng
    # ──────────────────────────────────────────

    # cinema_rooms.theater_id → theaters.id
    op.drop_constraint("cinema_rooms_theater_id_fkey", "cinema_rooms", type_="foreignkey")
    op.create_foreign_key(
        "cinema_rooms_theater_id_fkey", "cinema_rooms",
        "theaters", ["theater_id"], ["id"],
        ondelete="CASCADE"
    )

    # seats.room_id → cinema_rooms.id
    op.drop_constraint("seats_room_id_fkey", "seats", type_="foreignkey")
    op.create_foreign_key(
        "seats_room_id_fkey", "seats",
        "cinema_rooms", ["room_id"], ["id"],
        ondelete="CASCADE"
    )

    # showtimes.film_id → films.id
    op.drop_constraint("showtimes_film_id_fkey", "showtimes", type_="foreignkey")
    op.create_foreign_key(
        "showtimes_film_id_fkey", "showtimes",
        "films", ["film_id"], ["id"],
        ondelete="CASCADE"
    )

    # showtimes.room_id → cinema_rooms.id
    op.drop_constraint("showtimes_room_id_fkey", "showtimes", type_="foreignkey")
    op.create_foreign_key(
        "showtimes_room_id_fkey", "showtimes",
        "cinema_rooms", ["room_id"], ["id"],
        ondelete="CASCADE"
    )

    # seat_status.seat_id → seats.id
    op.drop_constraint("seat_status_seat_id_fkey", "seat_status", type_="foreignkey")
    op.create_foreign_key(
        "seat_status_seat_id_fkey", "seat_status",
        "seats", ["seat_id"], ["id"],
        ondelete="CASCADE"
    )

    # seat_status.showtime_id → showtimes.id
    op.drop_constraint("seat_status_showtime_id_fkey", "seat_status", type_="foreignkey")
    op.create_foreign_key(
        "seat_status_showtime_id_fkey", "seat_status",
        "showtimes", ["showtime_id"], ["id"],
        ondelete="CASCADE"
    )

    # seat_status.hold_by_user_id → users.id (SET NULL khi xóa user)
    op.drop_constraint("seat_status_hold_by_user_id_fkey", "seat_status", type_="foreignkey")
    op.create_foreign_key(
        "seat_status_hold_by_user_id_fkey", "seat_status",
        "users", ["hold_by_user_id"], ["id"],
        ondelete="SET NULL"
    )

    # bookings.user_id → users.id (RESTRICT — không cho xóa user còn booking)
    op.drop_constraint("bookings_user_id_fkey", "bookings", type_="foreignkey")
    op.create_foreign_key(
        "bookings_user_id_fkey", "bookings",
        "users", ["user_id"], ["id"],
        ondelete="RESTRICT"
    )

    # bookings.showtime_id → showtimes.id
    op.drop_constraint("bookings_showtime_id_fkey", "bookings", type_="foreignkey")
    op.create_foreign_key(
        "bookings_showtime_id_fkey", "bookings",
        "showtimes", ["showtime_id"], ["id"],
        ondelete="CASCADE"
    )

    # booking_details.booking_id → bookings.id
    op.drop_constraint("booking_details_booking_id_fkey", "booking_details", type_="foreignkey")
    op.create_foreign_key(
        "booking_details_booking_id_fkey", "booking_details",
        "bookings", ["booking_id"], ["id"],
        ondelete="CASCADE"
    )

    # booking_details.seat_id → seats.id
    op.drop_constraint("booking_details_seat_id_fkey", "booking_details", type_="foreignkey")
    op.create_foreign_key(
        "booking_details_seat_id_fkey", "booking_details",
        "seats", ["seat_id"], ["id"],
        ondelete="CASCADE"
    )

    # ──────────────────────────────────────────
    # 4. Xóa index đơn thừa (đã có composite hoặc unique constraint)
    # ──────────────────────────────────────────

    # ix_seat_status_seat_id thừa — ít khi query chỉ theo seat_id
    # mà luôn kèm showtime_id (đã có uq_seat_showtime)
    # Giữ lại vì có thể dùng cho JOIN booking_details → seat_status


def downgrade() -> None:
    """Rollback các thay đổi tối ưu."""

    # Drop composite indexes
    op.drop_index("ix_seat_status_hold_expired", table_name="seat_status")
    op.drop_index("ix_bookings_user_date", table_name="bookings")
    op.drop_index("ix_films_release_end_date", table_name="films")
    op.drop_index("ix_seat_status_showtime_status", table_name="seat_status")
    op.drop_index("ix_showtimes_film_date_status", table_name="showtimes")

    # Revert Numeric → Float
    op.alter_column("seats", "price", type_=sa.Float(), existing_type=sa.Numeric(12, 2))
    op.alter_column("booking_details", "price", type_=sa.Float(), existing_type=sa.Numeric(12, 2))
    op.alter_column("bookings", "total_amount", type_=sa.Float(), existing_type=sa.Numeric(12, 2))
    op.alter_column("theaters", "rating", type_=sa.Float(), existing_type=sa.Numeric(3, 1))

    # Revert FK constraints (remove CASCADE, back to default)
    for table, col, ref_table in [
        ("cinema_rooms", "theater_id", "theaters"),
        ("seats", "room_id", "cinema_rooms"),
        ("showtimes", "film_id", "films"),
        ("showtimes", "room_id", "cinema_rooms"),
        ("seat_status", "seat_id", "seats"),
        ("seat_status", "showtime_id", "showtimes"),
        ("seat_status", "hold_by_user_id", "users"),
        ("bookings", "user_id", "users"),
        ("bookings", "showtime_id", "showtimes"),
        ("booking_details", "booking_id", "bookings"),
        ("booking_details", "seat_id", "seats"),
    ]:
        constraint_name = f"{table}_{col}_fkey"
        op.drop_constraint(constraint_name, table, type_="foreignkey")
        op.create_foreign_key(
            constraint_name, table,
            ref_table, [col], ["id"]
        )
