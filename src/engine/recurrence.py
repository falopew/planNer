"""Strict RRULE subset and finite, shared occurrence-start expansion."""

import re
from datetime import date, datetime, time, timedelta

from dateutil.rrule import DAILY, MO, MONTHLY, WEEKLY, rrule

from src.models.recurrence import RecurrencePattern, RecurrenceValidationError

WEEKDAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
FREQUENCIES = {"daily": DAILY, "weekly": WEEKLY, "monthly": MONTHLY}


def _local(value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is not None:
        raise RecurrenceValidationError("Recurrence requires local date and time.")


def build_recurrence_rule(pattern: RecurrencePattern, dtstart: datetime) -> str:
    """Build the portable subset we support; do not persist a duplicate DTSTART."""
    _local(dtstart)
    if pattern.frequency not in FREQUENCIES:
        raise RecurrenceValidationError("Choose daily, weekly or monthly recurrence.")
    if type(pattern.interval) is not int or pattern.interval < 1:
        raise RecurrenceValidationError("Repeat interval must be a positive integer.")
    if pattern.weekdays is not None:
        if pattern.frequency != "weekly":
            raise RecurrenceValidationError(
                "Weekday selection requires weekly recurrence."
            )
        if not pattern.weekdays or any(
            type(day) is not int or day not in range(7) for day in pattern.weekdays
        ):
            raise RecurrenceValidationError("Select at least one valid weekday.")
    if pattern.end_date is not None:
        if type(pattern.end_date) is not date:
            raise RecurrenceValidationError("Choose a valid recurrence end date.")
        if pattern.end_date < dtstart.date():
            raise RecurrenceValidationError(
                "Recurrence end date cannot precede the start."
            )
    parts = [f"FREQ={pattern.frequency.upper()}", f"INTERVAL={pattern.interval}"]
    if pattern.weekdays is not None:
        parts.append(
            "BYDAY=" + ",".join(WEEKDAYS[d] for d in sorted(set(pattern.weekdays)))
        )
    if pattern.end_date is not None:
        # RRULE precision is seconds; this includes every start on the selected date.
        end = pattern.end_date
        parts.append(f"UNTIL={end.year:04d}{end.month:02d}{end.day:02d}T235959")
    return ";".join(parts)


def parse_recurrence_rule(rule: str, dtstart: datetime) -> RecurrencePattern:
    """Reject unsupported clauses rather than silently broadening a stored series."""
    _local(dtstart)
    try:
        if not isinstance(rule, str) or not rule or len(rule) > 250:
            raise ValueError
        parts: dict[str, str] = {}
        for clause in rule.split(";"):
            key, value = clause.split("=")
            if key in parts or key not in {"FREQ", "INTERVAL", "BYDAY", "UNTIL"}:
                raise ValueError
            parts[key] = value
        frequency = parts["FREQ"].lower()
        interval_text = parts.get("INTERVAL", "1")
        if not re.fullmatch(r"[0-9]+", interval_text):
            raise ValueError
        weekdays = None
        if "BYDAY" in parts:
            weekdays = tuple(WEEKDAYS.index(day) for day in parts["BYDAY"].split(","))
        end_date = None
        if "UNTIL" in parts:
            # UI supports a date, not an arbitrary end-time, UTC or COUNT.
            if not re.fullmatch(r"[0-9]{8}T235959", parts["UNTIL"]):
                raise ValueError
            end_date = datetime.strptime(parts["UNTIL"], "%Y%m%dT%H%M%S").date()
        pattern = RecurrencePattern(frequency, int(interval_text), weekdays, end_date)
        build_recurrence_rule(pattern, dtstart)
        return pattern
    except RecurrenceValidationError:
        raise
    except (ValueError, KeyError, TypeError, OverflowError) as error:
        raise RecurrenceValidationError(
            "Invalid or unsupported recurrence rule."
        ) from error


def normalize_recurrence_rule(rule: str | None, dtstart: datetime) -> str | None:
    if rule is None:
        return None
    return build_recurrence_rule(parse_recurrence_rule(rule, dtstart), dtstart)


def _window_anchor(
    base: datetime, pattern: RecurrencePattern, lower: datetime
) -> datetime:
    """Skip whole frequency cycles without changing their original phase.

    Safe only for our subset (no COUNT, exceptions or positional rules). Explicit
    BYDAY/BYMONTHDAY below preserve defaults that otherwise depend on DTSTART.
    """
    lower = max(base, lower)
    if pattern.frequency == "daily":
        cycles = (lower.date() - base.date()).days // pattern.interval
        return base + timedelta(days=cycles * pattern.interval)
    if pattern.frequency == "weekly":
        base_monday = base.date() - timedelta(days=base.weekday())
        weeks = (lower.date() - base_monday).days // 7
        anchor = base_monday + timedelta(
            weeks=(weeks // pattern.interval) * pattern.interval
        )
        return max(base, datetime.combine(anchor, base.time()))
    months = (lower.year - base.year) * 12 + lower.month - base.month
    month_index = (
        base.year * 12
        + base.month
        - 1
        + (months // pattern.interval) * pattern.interval
    )
    year, month = divmod(month_index, 12)
    return max(base, datetime.combine(date(year, month + 1, 1), base.time()))


def generate_occurrences(
    dtstart: datetime,
    recurrence_rule: str | None,
    range_start: datetime,
    range_end: datetime,
) -> list[datetime]:
    """Return starts in [range_start, range_end); never materialize a whole series."""
    for value in (dtstart, range_start, range_end):
        _local(value)
    if range_end < range_start:
        raise RecurrenceValidationError("Range end cannot precede range start.")
    pattern = (
        parse_recurrence_rule(recurrence_rule, dtstart)
        if recurrence_rule is not None
        else None
    )
    if range_end == range_start or dtstart >= range_end:
        return []
    if pattern is None:
        return [dtstart] if range_start <= dtstart < range_end else []
    limit = range_end
    if pattern.end_date is not None:
        limit = min(limit, datetime.combine(pattern.end_date, time.max))
    if limit < range_start:
        return []
    anchor = _window_anchor(dtstart, pattern, range_start)
    rule = rrule(
        FREQUENCIES[pattern.frequency],
        dtstart=anchor,
        interval=pattern.interval,
        wkst=MO,
        until=limit,
        byweekday=(pattern.weekdays or (dtstart.weekday(),))
        if pattern.frequency == "weekly"
        else None,
        bymonthday=dtstart.day if pattern.frequency == "monthly" else None,
    )
    # dateutil strips fractional seconds; retain the stored anchor's precision.
    occurrences = []
    for raw in rule:
        moment = raw.replace(microsecond=dtstart.microsecond)
        if range_start <= moment < range_end and dtstart <= moment <= limit:
            occurrences.append(moment)
    return occurrences
