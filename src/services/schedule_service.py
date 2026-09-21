"""Chronological display composition, not an occupancy or scheduling engine."""

from datetime import datetime

from src.models.event import Event
from src.models.reminder import Reminder
from src.services.event_service import EventService
from src.services.reminder_service import ReminderService


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
