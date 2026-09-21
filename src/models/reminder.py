"""Reminders are point-in-time information, never occupied intervals."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class ReminderInput:
    title: str
    reminder_datetime: datetime | None
    description: str = ""
    category: str = "Other"
    recurrence_rule: str | None = None


@dataclass(frozen=True, kw_only=True)
class Reminder(ReminderInput):
    reminder_datetime: datetime
    id: int
    created_at: datetime
    updated_at: datetime
