"""Shared repeat controls. RRULE building/parsing stays in the domain engine."""

from dataclasses import dataclass
from datetime import date, datetime

import streamlit as st

from src.engine.recurrence import build_recurrence_rule, parse_recurrence_rule
from src.models.recurrence import RecurrencePattern, RecurrenceValidationError

DAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
OPTIONS = (
    "Does not repeat",
    "Daily",
    "Weekdays",
    "Weekly",
    "Custom weekly",
    "Monthly",
    "Custom interval",
)


@dataclass(frozen=True)
class RecurrenceSelection:
    pattern: RecurrencePattern
    missing_end_date: bool = False


def render_recurrence_controls(
    key: str, rule: str | None, anchor: datetime | None
) -> RecurrenceSelection | None:
    """Collect structured settings; validation runs only on explicit Save/Create."""
    existing = parse_recurrence_rule(rule, anchor) if rule and anchor else None
    selected = "Does not repeat"
    if existing:
        if existing.weekdays is not None:
            selected = (
                "Weekdays"
                if existing.weekdays == (0, 1, 2, 3, 4) and existing.interval == 1
                else "Custom weekly"
            )
        elif existing.interval != 1:
            selected = "Custom interval"
        else:
            selected = existing.frequency.title()
    repeat = st.selectbox(
        "Repeat", OPTIONS, index=OPTIONS.index(selected), key=f"{key}_repeat"
    )
    if repeat == "Does not repeat":
        return None
    frequency = {
        "Daily": "daily",
        "Weekdays": "weekly",
        "Weekly": "weekly",
        "Custom weekly": "weekly",
        "Monthly": "monthly",
    }.get(repeat, "daily")
    interval = 1
    weekdays = None
    if repeat == "Weekdays":
        weekdays = (0, 1, 2, 3, 4)
    if repeat == "Custom weekly":
        chosen = st.multiselect(
            "Repeat on",
            DAY_NAMES,
            default=[DAY_NAMES[d] for d in existing.weekdays]
            if existing and existing.weekdays is not None
            else [],
            key=f"{key}_weekdays",
        )
        weekdays = tuple(DAY_NAMES.index(name) for name in chosen)
        interval = st.number_input(
            "Every N weeks",
            min_value=1,
            step=1,
            value=existing.interval if existing else 1,
            key=f"{key}_weeks",
        )
    if repeat == "Custom interval":
        interval = st.number_input(
            "Every",
            min_value=1,
            step=1,
            value=existing.interval if existing else 1,
            key=f"{key}_interval",
        )
        units = ("days", "weeks", "months")
        frequencies = ("daily", "weekly", "monthly")
        unit = st.selectbox(
            "Interval unit",
            units,
            index=frequencies.index(existing.frequency) if existing else 0,
            key=f"{key}_unit",
        )
        frequency = frequencies[units.index(unit)]
    ends = st.selectbox(
        "Ends",
        ("Never", "On date"),
        index=1 if existing and existing.end_date else 0,
        key=f"{key}_ends",
    )
    end_date = None
    if ends == "On date":
        end_date = st.date_input(
            "Recurrence end date",
            value=existing.end_date
            if existing and existing.end_date
            else (anchor.date() if anchor else date.today()),
            key=f"{key}_until",
        )
    return RecurrenceSelection(
        RecurrencePattern(frequency, int(interval), weekdays, end_date),
        missing_end_date=ends == "On date" and end_date is None,
    )


def rule_from_controls(
    selection: RecurrenceSelection | None, anchor: datetime | None
) -> str | None:
    if selection is None:
        return None
    if selection.missing_end_date:
        raise RecurrenceValidationError("Choose a recurrence end date.")
    if anchor is None:
        raise RecurrenceValidationError(
            "Choose the item's date and time before repeating."
        )
    return build_recurrence_rule(selection.pattern, anchor)
