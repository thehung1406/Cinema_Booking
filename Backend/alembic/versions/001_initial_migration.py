"""Initial migration with all models

Revision ID: 001
Revises:
Create Date: 2026-01-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create User table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('password', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('phone', sa.String(length=15), nullable=True),
        sa.Column('full_name', sa.String(length=100), nullable=True),
        sa.Column('avatar', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='USER'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Create Film table
    op.create_table(
        'films',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('image', sa.String(length=255), nullable=True),
        sa.Column('rating', sa.String(length=10), nullable=True),
        sa.Column('duration', sa.String(length=20), nullable=True),
        sa.Column('genre', sa.String(length=100), nullable=True),
        sa.Column('language', sa.String(length=50), nullable=True),
        sa.Column('subtitle', sa.String(length=50), nullable=True),
        sa.Column('formats', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('release_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('trailer', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create Theater table
    op.create_table(
        'theaters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('address', sa.String(length=255), nullable=False),
        sa.Column('city', sa.String(length=50), nullable=False),
        sa.Column('image', sa.String(length=255), nullable=True),
        sa.Column('rating', sa.Float(), nullable=True),
        sa.Column('technologies', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('special', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create Cinema Room table
    op.create_table(
        'cinema_rooms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('theater_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False),
        sa.Column('room_type', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['theater_id'], ['theaters.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cinema_rooms_theater_id'), 'cinema_rooms', ['theater_id'])

    # Create Seat table
    op.create_table(
        'seats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('room_id', sa.Integer(), nullable=False),
        sa.Column('seat_name', sa.String(length=10), nullable=False),
        sa.Column('seat_type', sa.String(length=20), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['room_id'], ['cinema_rooms.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_seats_room_id'), 'seats', ['room_id'])

    # Create Showtime table
    op.create_table(
        'showtimes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('film_id', sa.Integer(), nullable=False),
        sa.Column('room_id', sa.Integer(), nullable=False),
        sa.Column('show_date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('format', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='ACTIVE'),
        sa.ForeignKeyConstraint(['film_id'], ['films.id'], ),
        sa.ForeignKeyConstraint(['room_id'], ['cinema_rooms.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_showtimes_film_id'), 'showtimes', ['film_id'])
    op.create_index(op.f('ix_showtimes_room_id'), 'showtimes', ['room_id'])

    # Create Seat Status table
    op.create_table(
        'seat_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('seat_id', sa.Integer(), nullable=False),
        sa.Column('showtime_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='AVAILABLE'),
        sa.Column('hold_by_user_id', sa.Integer(), nullable=True),
        sa.Column('hold_expired_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['seat_id'], ['seats.id'], ),
        sa.ForeignKeyConstraint(['showtime_id'], ['showtimes.id'], ),
        sa.ForeignKeyConstraint(['hold_by_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('showtime_id', 'seat_id', name='uq_seat_showtime')
    )
    op.create_index(op.f('ix_seat_status_seat_id'), 'seat_status', ['seat_id'])
    op.create_index(op.f('ix_seat_status_showtime_id'), 'seat_status', ['showtime_id'])

    # Create Booking table
    op.create_table(
        'bookings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('showtime_id', sa.Integer(), nullable=False),
        sa.Column('booking_date', sa.DateTime(), nullable=False),
        sa.Column('total_amount', sa.Float(), nullable=False),
        sa.Column('payment_method', sa.String(length=50), nullable=True),
        sa.Column('payment_status', sa.String(length=20), nullable=False, server_default='PENDING'),
        sa.Column('booking_status', sa.String(length=20), nullable=False, server_default='PENDING'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['showtime_id'], ['showtimes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bookings_user_id'), 'bookings', ['user_id'])
    op.create_index(op.f('ix_bookings_showtime_id'), 'bookings', ['showtime_id'])

    # Create Booking Detail table
    op.create_table(
        'booking_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('booking_id', sa.Integer(), nullable=False),
        sa.Column('seat_id', sa.Integer(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ),
        sa.ForeignKeyConstraint(['seat_id'], ['seats.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_booking_details_booking_id'), 'booking_details', ['booking_id'])
    op.create_index(op.f('ix_booking_details_seat_id'), 'booking_details', ['seat_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_booking_details_seat_id'), table_name='booking_details')
    op.drop_index(op.f('ix_booking_details_booking_id'), table_name='booking_details')
    op.drop_table('booking_details')
    op.drop_index(op.f('ix_bookings_showtime_id'), table_name='bookings')
    op.drop_index(op.f('ix_bookings_user_id'), table_name='bookings')
    op.drop_table('bookings')
    op.drop_index(op.f('ix_seat_status_showtime_id'), table_name='seat_status')
    op.drop_index(op.f('ix_seat_status_seat_id'), table_name='seat_status')
    op.drop_table('seat_status')
    op.drop_index(op.f('ix_showtimes_room_id'), table_name='showtimes')
    op.drop_index(op.f('ix_showtimes_film_id'), table_name='showtimes')
    op.drop_table('showtimes')
    op.drop_index(op.f('ix_seats_room_id'), table_name='seats')
    op.drop_table('seats')
    op.drop_index(op.f('ix_cinema_rooms_theater_id'), table_name='cinema_rooms')
    op.drop_table('cinema_rooms')
    op.drop_table('theaters')
    op.drop_table('films')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')

