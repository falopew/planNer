"""Chronological display composition, not an occupancy or scheduling engine."""

from dataclasses import replace
from datetime import date, datetime, timedelta

from src.engine.recurrence import generate_occurrences
from src.models.event import Event
from src.models.reminder import Reminder
from src.services.event_service import EventService
from src.services.reminder_service import ReminderService
from src.utils.time_utils import get_day_bounds, get_week_bounds


def _display_order(item: Event | Reminder) -> tuple[datetime, int, int]:
    if isinstance(item, Event):
        return item.start_datetime, 0, item.id
    return item.reminder_datetime, 1, item.id


def occurrence_identity(item: Event | Reminder) -> tuple[str, int, datetime]:
    """id is always the persisted SOURCE id, never a fake occurrence row id."""
    if isinstance(item, Event):
        return "event", item.id, item.start_datetime
    return "reminder", item.id, item.reminder_datetime


def _in_range(item: Event | Reminder, start: datetime, end: datetime) -> bool:
    if isinstance(item, Event):
        return item.start_datetime < end and item.end_datetime > start
    return start <= item.reminder_datetime < end


class ScheduleService:
    def __init__(self, events: EventService, reminders: ReminderService) -> None:
        self._events = events
        self._reminders = reminders

    def list_items(self) -> list[Event | Reminder]:
        """Return stored base items for CRUD, NOT an unbounded expanded schedule."""
        items: list[Event | Reminder] = [
            *self._events.list_events(),
            *self._reminders.list_reminders(),
        ]
        return sorted(items, key=_display_order)

    def get_schedule_between(
        self, start: datetime, end: datetime
    ) -> list[Event | Reminder]:
        """Return ordinary rows and virtual copies, with source IDs preserved."""
        items: list[Event | Reminder] = [
            item
            for item in [
                *self._events.get_events_between(start, end),
                *self._reminders.get_reminders_between(start, end),
            ]
            if item.recurrence_rule is None
        ]
        for event in self._events.list_recurring_events(end):
            duration = event.end_datetime - event.start_datetime
            lower = start - min(duration, start - datetime.min)
            for moment in generate_occurrences(
                event.start_datetime, event.recurrence_rule, lower, end
            ):
                # Do not manufacture an unrepresentable datetime beyond year 9999.
                if duration > datetime.max - moment:
                    continue
                occurrence = replace(
                    event, start_datetime=moment, end_datetime=moment + duration
                )
                if _in_range(occurrence, start, end):
                    items.append(occurrence)
        for reminder in self._reminders.list_recurring_reminders(end):
            items.extend(
                replace(reminder, reminder_datetime=moment)
                for moment in generate_occurrences(
                    reminder.reminder_datetime, reminder.recurrence_rule, start, end
                )
            )
        return sorted(items, key=_display_order)

    def get_day_schedule(self, day: date) -> list[Event | Reminder]:
        return self.get_schedule_between(*get_day_bounds(day))

    def get_week_schedule(self, day: date) -> dict[date, list[Event | Reminder]]:
        """Seven Monday–Sunday agendas, including empty days.

        Fetch/expand once for the whole week, then group using the same semantics.
        An overnight event appears once on each day it overlaps, unchanged.
        """
        start, end = get_week_bounds(day)
        items = self.get_schedule_between(start, end)
        monday = start.date()
        days = {}
        for offset in range(7):
            selected = monday + timedelta(days=offset)
            lower, upper = get_day_bounds(selected)
            days[selected] = [item for item in items if _in_range(item, lower, upper)]
        return days
