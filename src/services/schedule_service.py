"""Chronological display composition, not an occupancy or scheduling engine."""

from datetime import date, datetime, timedelta

from src.models.event import Event
from src.models.reminder import Reminder
from src.services.event_service import EventService
from src.services.reminder_service import ReminderService
from src.utils.time_utils import get_day_bounds, get_week_start


def _display_order(item: Event | Reminder) -> tuple[datetime, int, int]:
    if isinstance(item, Event):
        return item.start_datetime, 0, item.id
    return item.reminder_datetime, 1, item.id


class ScheduleService:
    def __init__(self, events: EventService, reminders: ReminderService) -> None:
        self._events = events
        self._reminders = reminders

    def list_items(self) -> list[Event | Reminder]:
        """Return distinct typed items; never convert reminders to event intervals."""
        items: list[Event | Reminder] = [
            *self._events.list_events(),
            *self._reminders.list_reminders(),
        ]
        return sorted(items, key=_display_order)

    def get_schedule_between(
        self, start: datetime, end: datetime
    ) -> list[Event | Reminder]:
        """Events overlap [start, end); reminders fall within it."""
        items: list[Event | Reminder] = [
            *self._events.get_events_between(start, end),
            *self._reminders.get_reminders_between(start, end),
        ]
        return sorted(items, key=_display_order)

    def get_day_schedule(self, day: date) -> list[Event | Reminder]:
        return self.get_schedule_between(*get_day_bounds(day))

    def get_week_schedule(self, day: date) -> dict[date, list[Event | Reminder]]:
        """Seven Monday–Sunday agendas, including empty days.

        Reuse bounded day queries rather than reimplement interval filtering.
        An overnight event appears once on each day it overlaps, unchanged.
        """
        monday = get_week_start(day)
        days = {}
        for offset in range(7):
            selected = monday + timedelta(days=offset)
            days[selected] = self.get_day_schedule(selected)
        return days
