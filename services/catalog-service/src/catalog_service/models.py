from datetime import date, datetime, time, timezone
from decimal import Decimal
from sqlalchemy import (CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    Integer, JSON, Numeric, String, Table, Column, Text, UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


film_genres = Table("film_genres", Base.metadata,
    Column("film_id", ForeignKey("films.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id", ondelete="RESTRICT"), primary_key=True))
film_formats = Table("film_formats", Base.metadata,
    Column("film_id", ForeignKey("films.id", ondelete="CASCADE"), primary_key=True),
    Column("format_id", ForeignKey("formats.id", ondelete="RESTRICT"), primary_key=True))


class Genre(Base):
    __tablename__ = "genres"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Format(Base):
    __tablename__ = "formats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(50))


class Film(Base):
    __tablename__ = "films"
    __table_args__ = (CheckConstraint("duration_minutes > 0", name="ck_film_duration_positive"),
        Index("ix_films_release_end_date", "release_date", "end_date"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    image: Mapped[str | None] = mapped_column(String(255))
    rating: Mapped[str | None] = mapped_column(String(10))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str | None] = mapped_column(String(50))
    subtitle: Mapped[str | None] = mapped_column(String(50))
    release_date: Mapped[date | None]
    end_date: Mapped[date | None]
    description: Mapped[str | None] = mapped_column(Text)
    trailer: Mapped[str | None] = mapped_column(String(255))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    catalog_version: Mapped[int] = mapped_column(default=1, server_default="1")
    genre_items: Mapped[list[Genre]] = relationship(secondary=film_genres, lazy="selectin", order_by="Genre.id")
    format_items: Mapped[list[Format]] = relationship(secondary=film_formats, lazy="selectin", order_by="Format.id")

    @property
    def genre(self):
        return ", ".join(item.name for item in self.genre_items) or None

    @property
    def formats(self):
        return [item.name for item in self.format_items]

    @property
    def duration(self):
        return f"{self.duration_minutes} phút" if self.duration_minutes is not None else None


class FoodItem(Base):
    __tablename__ = "food_items"
    __table_args__ = (CheckConstraint("price > 0", name="ck_food_price"),
        CheckConstraint("category IN ('POPCORN', 'DRINK', 'COMBO')", name="ck_food_category"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(String(500), default="")
    category: Mapped[str] = mapped_column(String(20))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    is_active: Mapped[bool] = mapped_column(default=True)
    catalog_version: Mapped[int] = mapped_column(default=1, server_default="1")


class ComboItem(Base):
    __tablename__ = "combo_items"
    __table_args__ = (UniqueConstraint("combo_id", "food_item_id", name="uq_combo_component"),
        CheckConstraint("quantity > 0", name="ck_combo_quantity"), CheckConstraint("combo_id <> food_item_id", name="ck_combo_not_self"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    combo_id: Mapped[int] = mapped_column(ForeignKey("food_items.id", ondelete="RESTRICT"), index=True)
    food_item_id: Mapped[int] = mapped_column(ForeignKey("food_items.id", ondelete="RESTRICT"), index=True)
    quantity: Mapped[int]


class ScheduleBinding(Base):
    __tablename__ = "schedule_bindings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    film_id: Mapped[int] = mapped_column(ForeignKey("films.id", ondelete="RESTRICT"), index=True)
    format_id: Mapped[int] = mapped_column(ForeignKey("formats.id", ondelete="RESTRICT"))
    show_date: Mapped[date]
    start_time: Mapped[time]
    end_time: Mapped[time]
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    reference_state: Mapped[str] = mapped_column(String(20), default="RESERVED", server_default="CONFIRMED")
    reference: Mapped[str | None] = mapped_column(String(100))
    film_version: Mapped[int]
    film_snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FoodQuote(Base):
    __tablename__ = "food_quotes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version: Mapped[int] = mapped_column(default=1)
    lines: Mapped[list] = mapped_column(JSON)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BindingClosure(Base):
    __tablename__ = "schedule_binding_closures"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    reference: Mapped[str] = mapped_column(String(100))
