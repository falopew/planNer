"""Shared recurrence settings, independent of UI and persistence."""

from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass(frozen=True)
class RecurrencePattern:
    frequency: Literal["daily", "weekly", "monthly"]
    interval: int = 1
    # Monday=0 through Sunday=6; None means the anchor weekday for weekly rules.
    weekdays: tuple[int, ...] | None = None
    end_date: date | None = None


class RecurrenceValidationError(ValueError):
    """A readable recurrence error, safe to display without parser internals."""
