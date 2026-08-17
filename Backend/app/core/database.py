from sqlmodel import SQLModel, Session, create_engine
from app.core.config import settings
import logging

# Import all models so Alembic & SQLModel know them
from app.models import (
    User, Film, Theater, CinemaRoom, SeatType, Seat,
    Showtime, SeatStatus, Booking, BookingDetail
)

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,  # Recycle connections sau 30 phút
)

def init_db() -> None:
    """
    Initialize database.
    Note: Tables are managed by Alembic migrations.
    This function is kept for compatibility.
    """
    logger.info("✅ Database initialized (managed by Alembic)")


def get_session():
    with Session(engine) as session:
        yield session


