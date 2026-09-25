"""Concrete Fixed Event persistence using one session per operation."""

from dataclasses import asdict
from datetime import datetime, timedelta

from sqlalchemy import Engine, select
from sqlalchemy.orm import sessionmaker

from src.database.models import EventRecord
from src.models.event import Event, EventInput


def _to_event(record: EventRecord) -> Event:
    return Event(
        id=record.id,
        title=record.title,
        description=record.description,
        start_datetime=record.start_datetime,
        end_datetime=record.end_datetime,
        category=record.category,
        location=record.location,
        created_at=record.created_at,
        updated_at=record.updated_at,
        recurrence_rule=record.recurrence_rule,
    )


class EventRepository:
    """Accept validated input from EventService; return detached plain data."""

    def __init__(self, engine: Engine) -> None:
        self._sessions = sessionmaker(bind=engine)

    def create_event(self, data: EventInput) -> Event:
        now = datetime.now()
        with self._sessions.begin() as session:
            record = EventRecord(**asdict(data), created_at=now, updated_at=now)
            session.add(record)
            session.flush()
            result = _to_event(record)
        return result

    def get_event(self, event_id: int) -> Event | None:
        with self._sessions() as session:
            record = session.get(EventRecord, event_id)
            return _to_event(record) if record else None

    def list_events(self) -> list[Event]:
        with self._sessions() as session:
            records = session.scalars(
                select(EventRecord).order_by(EventRecord.start_datetime, EventRecord.id)
            )
            return [_to_event(record) for record in records]

    def get_events_between(self, start: datetime, end: datetime) -> list[Event]:
        """Include any event overlapping the half-open range [start, end)."""
        with self._sessions() as session:
            records = session.scalars(
                select(EventRecord)
                .where(
                    EventRecord.start_datetime < end,
                    EventRecord.end_datetime > start,
                )
                .order_by(EventRecord.start_datetime, EventRecord.id)
            )
            return [_to_event(record) for record in records]

    def update_event(self, event_id: int, data: EventInput) -> Event | None:
        with self._sessions.begin() as session:
            record = session.get(EventRecord, event_id)
            if record is None:
                return None
            for field, value in asdict(data).items():
                setattr(record, field, value)
            # Ensure even same-clock-tick edits refresh the timestamp.
            record.updated_at = max(
                datetime.now(), record.updated_at + timedelta(microseconds=1)
            )
            session.flush()
            result = _to_event(record)
        return result

    def list_recurring_events(self, before: datetime) -> list[Event]:
        """Load candidate base series once, including anchors before the window."""
        with self._sessions() as session:
            records = session.scalars(
                select(EventRecord).where(
                    EventRecord.recurrence_rule.is_not(None),
                    EventRecord.start_datetime < before,
                )
            )
            return [_to_event(record) for record in records]

    def delete_event(self, event_id: int) -> bool:
        with self._sessions.begin() as session:
            record = session.get(EventRecord, event_id)
            if record is None:
                return False
            session.delete(record)
        return True
