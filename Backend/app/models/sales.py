from datetime import date, datetime, time, timezone
from sqlalchemy import DateTime, Integer, JSON, String, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class SalesBase(DeclarativeBase):
    pass


class SalesConfiguration(SalesBase):
    __tablename__ = "booking_sales_configurations"
    showtime_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sales_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    digest: Mapped[str] = mapped_column(String(64))
    film_id: Mapped[int] = mapped_column(Integer, index=True)
    room_id: Mapped[int] = mapped_column(Integer, index=True)
    theater_id: Mapped[int] = mapped_column(Integer, index=True)
    show_date: Mapped[date]
    start_time: Mapped[time]
    end_time: Mapped[time]
    status: Mapped[str] = mapped_column(String(20))
    snapshot: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @property
    def id(self): return self.showtime_id

    @property
    def format(self): return self.snapshot["film"]["format_name"]

    @property
    def format_id(self): return self.snapshot["format_id"]

    @property
    def catalog_film_snapshot(self): return self.snapshot["film"]


class SalesGate(SalesBase):
    __tablename__ = "booking_sales_gates"
    __table_args__ = (ForeignKeyConstraint(["showtime_id", "sales_version"],
        ["booking_sales_configurations.showtime_id", "booking_sales_configurations.sales_version"], ondelete="RESTRICT"),)
    showtime_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sales_version: Mapped[int | None] = mapped_column(Integer)
    epoch: Mapped[int] = mapped_column(Integer, default=0)
    action: Mapped[str] = mapped_column(String(20), default="INIT")
    is_open: Mapped[bool] = mapped_column(default=False)
