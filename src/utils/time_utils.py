"""Local calendar boundaries; ranges always exclude their end."""

from datetime import date, datetime, time, timedelta


def get_day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min)
    return start, start + timedelta(days=1)


def get_week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def get_week_bounds(day: date) -> tuple[datetime, datetime]:
    start, _ = get_day_bounds(get_week_start(day))
    return start, start + timedelta(days=7)
