"""Forms and cards for Fixed Events. All operations go through EventService."""

from dataclasses import replace
from datetime import date, datetime, time

import streamlit as st

from src.models.event import Event, EventInput
from src.models.recurrence import RecurrenceValidationError
from src.services.event_service import (
    EventService,
    EventStorageError,
    EventValidationError,
)
from src.ui.categories import CATEGORIES
from src.ui.recurrence import render_recurrence_controls, rule_from_controls


def _finish(message: str) -> None:
    st.session_state.pop("editing_event_id", None)
    st.session_state.pop("delete_event_id", None)
    st.session_state["event_notice"] = message
    st.session_state["event_form_version"] = (
        st.session_state.get("event_form_version", 0) + 1
    )
    st.rerun()


def _event_form(service: EventService, event: Event | None) -> None:
    st.subheader(f"Edit event: {event.title}" if event else "Add a Fixed Event")
    if event and st.button("Cancel editing"):
        _finish("Editing cancelled.")
    version = st.session_state.get("event_form_version", 0)
    form_key = f"event_form_{event.id if event else 'new'}_{version}"
    categories = list(CATEGORIES)
    if event and event.category not in categories:
        categories.append(event.category)
    with st.container():
        title = st.text_input(
            "Title",
            value=event.title if event else "",
            max_chars=200,
            key=f"{form_key}_title",
        )
        description = st.text_area(
            "Description",
            value=event.description if event else "",
            key=f"{form_key}_description",
        )
        day = st.date_input(
            "Date",
            value=event.start_datetime.date() if event else date.today(),
            key=f"{form_key}_date",
        )
        start = st.time_input(
            "Start time",
            value=event.start_datetime.time() if event else time(9),
            key=f"{form_key}_start",
        )
        end = st.time_input(
            "End time",
            value=event.end_datetime.time() if event else time(10),
            key=f"{form_key}_end",
        )
        # Preserve a multi-day event supplied through the service API when editing.
        end_day = day
        if event and event.end_datetime.date() != event.start_datetime.date():
            end_day = st.date_input(
                "End date", value=event.end_datetime.date(), key=f"{form_key}_end_date"
            )
        category = st.selectbox(
            "Category",
            categories,
            index=categories.index(event.category if event else "Other"),
            key=f"{form_key}_category",
        )
        location = st.text_input(
            "Location",
            value=event.location if event else "",
            key=f"{form_key}_location",
        )
        recurrence = render_recurrence_controls(
            form_key,
            event.recurrence_rule if event else None,
            event.start_datetime if event else None,
        )
        if event and event.recurrence_rule:
            st.caption("Editing recurrence changes the entire series.")
        submitted = st.button(
            "Save changes" if event else "Create event", key=f"{form_key}_save"
        )
    if not submitted:
        return
    data = EventInput(
        title=title,
        description=description,
        start_datetime=(
            datetime.combine(day, start)
            if day is not None and start is not None
            else None
        ),
        end_datetime=(
            datetime.combine(end_day, end)
            if end_day is not None and end is not None
            else None
        ),
        category=category,
        location=location,
    )
    try:
        data = replace(
            data, recurrence_rule=rule_from_controls(recurrence, data.start_datetime)
        )
        if event:
            saved = service.update_event(event.id, data)
            message = "Event updated." if saved else "That event no longer exists."
        else:
            service.create_event(data)
            message = "Event created."
    except (
        EventValidationError,
        EventStorageError,
        RecurrenceValidationError,
    ) as error:
        st.error(str(error))
        return
    _finish(message)


def _confirm_delete(service: EventService) -> None:
    event_id = st.session_state.get("delete_event_id")
    if event_id is None:
        return
    event = service.get_event(event_id)
    if event is None:
        st.session_state.pop("delete_event_id", None)
        st.info("That event no longer exists.")
        return
    st.warning(f'Delete "{event.title}"? This cannot be undone.')
    if event.recurrence_rule:
        st.warning("This will delete the recurring series and all its occurrences.")
    if st.button("Confirm deletion", key=f"confirm_delete_{event.id}"):
        deleted = service.delete_event(event.id)
        _finish("Event deleted." if deleted else "That event no longer exists.")
    if st.button("Cancel deletion"):
        st.session_state.pop("delete_event_id", None)
        st.rerun()


def _select_event(event_id: int, action: str) -> None:
    st.session_state["item_type"] = "Fixed Event"
    st.session_state[f"{action}_event_id"] = event_id
    if action == "editing":
        st.session_state.pop("delete_event_id", None)


def render_event_card(event: Event) -> None:
    with st.container(border=True):
        st.subheader(event.title)
        st.write(
            f"{event.start_datetime:%d %b %Y, %H:%M} – "
            f"{event.end_datetime:%d %b %Y, %H:%M}"
        )
        st.write(f"Category: {event.category}")
        if event.location:
            st.write(f"Location: {event.location}")
        if event.recurrence_rule:
            st.caption("Repeating series · edit/delete affects all occurrences")
        if event.description:
            st.write(event.description)
        st.button(
            "Edit",
            key=f"edit_{event.id}",
            on_click=_select_event,
            args=(event.id, "editing"),
        )
        st.button(
            "Delete",
            key=f"delete_{event.id}",
            on_click=_select_event,
            args=(event.id, "delete"),
        )


def render_event_editor(service: EventService) -> None:
    """Render one create/edit form and its deletion confirmation."""
    if notice := st.session_state.pop("event_notice", None):
        st.success(notice)
    try:
        editing_id = st.session_state.get("editing_event_id")
        event = service.get_event(editing_id) if editing_id is not None else None
        if editing_id is not None and event is None:
            st.session_state.pop("editing_event_id", None)
            st.info("That event no longer exists.")
        _event_form(service, event)
        _confirm_delete(service)
    except (EventStorageError, RecurrenceValidationError) as error:
        st.error(str(error))
