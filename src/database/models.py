"""SQLAlchemy mappings for implemented tables only."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EventRecord(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 200", name="event_title"),
        CheckConstraint("end_datetime > start_datetime", name="event_interval"),
        CheckConstraint("length(trim(category)) > 0", name="event_category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    start_datetime: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_datetime: Mapped[datetime] = mapped_column(DateTime)
    category: Mapped[str] = mapped_column(String, default="Other")
    location: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
