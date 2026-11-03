"""Read-only conflict results; never database records."""

from dataclasses import dataclass
from datetime import date, datetime

from src.models.event import Event
from src.models.reminder import Reminder


@dataclass(frozen=True)
class EventConflict:
    first: Event
    second: Event
    overlap_start: datetime
    overlap_end: datetime


@dataclass(frozen=True)
class DayAgenda:
    items: list[Event | Reminder]
    conflicts: list[EventConflict]


@dataclass(frozen=True)
class WeekAgenda:
    days: dict[date, list[Event | Reminder]]
    conflicts: list[EventConflict]
