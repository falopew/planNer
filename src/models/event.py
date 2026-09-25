"""Plain application data; deliberately independent of SQLAlchemy and Streamlit."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class EventInput:
    title: str
    start_datetime: datetime | None
    end_datetime: datetime | None
    description: str = ""
    category: str = "Other"
    location: str = ""
    recurrence_rule: str | None = None


@dataclass(frozen=True, kw_only=True)
class Event(EventInput):
    start_datetime: datetime
    end_datetime: datetime
    id: int
    created_at: datetime
    updated_at: datetime
