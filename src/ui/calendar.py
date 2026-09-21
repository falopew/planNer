"""Read-only agenda views. Selection and range filtering belong to services."""

from datetime import date, timedelta

import streamlit as st

from src.models.event import Event
from src.models.reminder import Reminder
from src.services.event_service import EventStorageError
from src.services.reminder_service import ReminderStorageError
from src.services.schedule_service import ScheduleService

# Leave space for exclusive day/week ends at the limits of Python's date range.
MIN_DATE = date.min + timedelta(days=7)
MAX_DATE = date.max - timedelta(days=7)


def local_today() -> date:
    """Read the local clock only at the presentation boundary."""
    return date.today()


def _set_date(key: str, selected: date) -> None:
    st.session_state[key] = selected


def _open_tomorrow(today: date) -> None:
    st.session_state["page"] = "Calendar"
    st.session_state["calendar_view"] = "Day"
    st.session_state["day_date"] = today + timedelta(days=1)


def _date_navigation(key: str, today: date, week: bool = False) -> date | None:
    st.session_state.setdefault(key, today)
    selected = st.session_state[key]
    anchor = selected or today
    step = timedelta(days=7 if week else 1)
    unit = "Week" if week else "Day"
    previous, current, following = st.columns(3)
    previous.button(
        f"Previous {unit}",
        key=f"{key}_previous",
        on_click=_set_date,
        args=(key, anchor - step),
        disabled=anchor - step < MIN_DATE,
    )
    current.button(
        "Current Week" if week else "Today",
        key=f"{key}_current",
        on_click=_set_date,
        args=(key, today),
    )
    following.button(
        f"Next {unit}",
        key=f"{key}_next",
        on_click=_set_date,
        args=(key, anchor + step),
        disabled=anchor + step > MAX_DATE,
    )
    return st.date_input(
        "Select a date in the week" if week else "Select date",
        key=key,
        min_value=MIN_DATE,
        max_value=MAX_DATE,
    )


def _render_items(items: list[Event | Reminder], empty_message: str) -> None:
    if not items:
        st.info(empty_message)
    for item in items:
        if isinstance(item, Event):
            with st.container(border=True):
                if item.start_datetime.date() == item.end_datetime.date():
                    interval = (
                        f"{item.start_datetime:%H:%M} – {item.end_datetime:%H:%M}"
                    )
                else:
                    # Preserve actual endpoints so overnight spans are unambiguous.
                    interval = (
                        f"{item.start_datetime:%d %b %Y %H:%M} – "
                        f"{item.end_datetime:%d %b %Y %H:%M}"
                    )
                st.caption(f"Fixed Event · {interval}")
                st.subheader(item.title)
                st.caption(item.category)
                if item.location:
                    st.text(f"Location: {item.location}")
                if item.description:
                    st.text(item.description)
        else:
            # No bordered duration block: a reminder is a single instant.
            st.subheader(f"🔔 {item.title}")
            st.caption(
                f"Reminder · {item.reminder_datetime:%H:%M} · "
                f"{item.category} · No occupied time"
            )
            if item.description:
                st.text(item.description)


def _render_day(service: ScheduleService, selected: date) -> None:
    st.header(selected.strftime("%A, %d %B %Y"))
    _render_items(
        service.get_day_schedule(selected), "No plans or reminders for this day."
    )


def render_today(service: ScheduleService) -> None:
    today = local_today()
    st.subheader("Today")
    st.button("Tomorrow", on_click=_open_tomorrow, args=(today,))
    try:
        _render_day(service, today)
    except (EventStorageError, ReminderStorageError) as error:
        st.error(str(error))


def render_calendar(service: ScheduleService) -> None:
    view = st.radio(
        "Calendar view", ("Day", "Week"), horizontal=True, key="calendar_view"
    )
    week = view == "Week"
    selected = _date_navigation(
        "week_date" if week else "day_date", local_today(), week=week
    )
    if selected is None:
        st.info("Choose a date to see your schedule.")
        return
    try:
        if not week:
            _render_day(service, selected)
            return
        days = service.get_week_schedule(selected)
        dates = list(days)
        st.header(f"Week: {dates[0]:%d %b %Y} – {dates[-1]:%d %b %Y}")
        for day, items in days.items():
            st.subheader(day.strftime("%A, %d %B"))
            _render_items(items, "No items")
    except (EventStorageError, ReminderStorageError) as error:
        st.error(str(error))
