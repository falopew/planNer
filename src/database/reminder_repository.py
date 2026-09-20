"""Concrete Reminder persistence using one session per operation."""

from dataclasses import asdict
from datetime import datetime, timedelta

from sqlalchemy import Engine, select
from sqlalchemy.orm import sessionmaker

from src.database.models import ReminderRecord
from src.models.reminder import Reminder, ReminderInput


def _to_reminder(record: ReminderRecord) -> Reminder:
    return Reminder(
        id=record.id,
        title=record.title,
        description=record.description,
        reminder_datetime=record.reminder_datetime,
        category=record.category,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class ReminderRepository:
    """Accept validated input from ReminderService; return detached plain data."""

    def __init__(self, engine: Engine) -> None:
        self._sessions = sessionmaker(bind=engine)

    def create_reminder(self, data: ReminderInput) -> Reminder:
        now = datetime.now()
        with self._sessions.begin() as session:
            record = ReminderRecord(**asdict(data), created_at=now, updated_at=now)
            session.add(record)
            session.flush()
            result = _to_reminder(record)
        return result

    def get_reminder(self, reminder_id: int) -> Reminder | None:
        with self._sessions() as session:
            record = session.get(ReminderRecord, reminder_id)
            return _to_reminder(record) if record else None

    def list_reminders(self) -> list[Reminder]:
        with self._sessions() as session:
            records = session.scalars(
                select(ReminderRecord).order_by(
                    ReminderRecord.reminder_datetime, ReminderRecord.id
                )
            )
            return [_to_reminder(record) for record in records]

    def get_reminders_between(self, start: datetime, end: datetime) -> list[Reminder]:
        """Select reminder instants inside the half-open range [start, end)."""
        with self._sessions() as session:
            records = session.scalars(
                select(ReminderRecord)
                .where(
                    ReminderRecord.reminder_datetime >= start,
                    ReminderRecord.reminder_datetime < end,
                )
                .order_by(ReminderRecord.reminder_datetime, ReminderRecord.id)
            )
            return [_to_reminder(record) for record in records]

    def update_reminder(self, reminder_id: int, data: ReminderInput) -> Reminder | None:
        with self._sessions.begin() as session:
            record = session.get(ReminderRecord, reminder_id)
            if record is None:
                return None
            for field, value in asdict(data).items():
                setattr(record, field, value)
            # Ensure even same-clock-tick edits refresh the timestamp.
            record.updated_at = max(
                datetime.now(), record.updated_at + timedelta(microseconds=1)
            )
            session.flush()
            result = _to_reminder(record)
        return result

    def delete_reminder(self, reminder_id: int) -> bool:
        with self._sessions.begin() as session:
            record = session.get(ReminderRecord, reminder_id)
            if record is None:
                return False
            session.delete(record)
        return True
