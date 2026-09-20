"""Forms and cards for Fixed Events. All operations go through EventService."""

from datetime import date, datetime, time

import streamlit as st

from src.models.event import Event, EventInput
from src.services.event_service import (
    EventService,
    EventStorageError,
    EventValidationError,
)

CATEGORIES = (
    "University",
    "Study",
    "Sport",
    "Work",
    "Personal",
    "Health",
    "Social",
    "Travel",
    "Other",
)


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
    with st.form(form_key):
        title = st.text_input(
            "Title", value=event.title if event else "", max_chars=200
        )
        description = st.text_area(
            "Description", value=event.description if event else ""
        )
        day = st.date_input(
            "Date", value=event.start_datetime.date() if event else date.today()
        )
        start = st.time_input(
            "Start time", value=event.start_datetime.time() if event else time(9)
        )
        end = st.time_input(
            "End time", value=event.end_datetime.time() if event else time(10)
        )
        # Preserve a multi-day event supplied through the service API when editing.
        end_day = day
        if event and event.end_datetime.date() != event.start_datetime.date():
            end_day = st.date_input("End date", value=event.end_datetime.date())
        category = st.selectbox(
            "Category",
            categories,
            index=categories.index(event.category if event else "Other"),
        )
        location = st.text_input("Location", value=event.location if event else "")
        submitted = st.form_submit_button("Save changes" if event else "Create event")
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
        if event:
            saved = service.update_event(event.id, data)
            message = "Event updated." if saved else "That event no longer exists."
        else:
            service.create_event(data)
            message = "Event created."
    except (EventValidationError, EventStorageError) as error:
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
    if st.button("Confirm deletion", key=f"confirm_delete_{event.id}"):
        deleted = service.delete_event(event.id)
        _finish("Event deleted." if deleted else "That event no longer exists.")
    if st.button("Cancel deletion"):
        st.session_state.pop("delete_event_id", None)
        st.rerun()


def _event_card(event: Event) -> None:
    with st.container(border=True):
        st.subheader(event.title)
        st.write(
            f"{event.start_datetime:%d %b %Y, %H:%M} – "
            f"{event.end_datetime:%d %b %Y, %H:%M}"
        )
        st.write(f"Category: {event.category}")
        if event.location:
            st.write(f"Location: {event.location}")
        if event.description:
            st.write(event.description)
        if st.button("Edit", key=f"edit_{event.id}"):
            st.session_state["editing_event_id"] = event.id
            st.session_state.pop("delete_event_id", None)
            st.rerun()
        if st.button("Delete", key=f"delete_{event.id}"):
            st.session_state["delete_event_id"] = event.id
            st.rerun()


def render_events(service: EventService) -> None:
    """Render one create/edit form, confirmation prompt, and chronological cards."""
    if notice := st.session_state.pop("event_notice", None):
        st.success(notice)
    try:
        editing_id = st.session_state.get("editing_event_id")
        event = service.get_event(editing_id) if editing_id is not None else None
        if editing_id is not None and event is None:
            st.session_state.pop("editing_event_id", None)
            st.info("That event no longer exists.")
        _event_form(service, event)
        st.subheader("Saved events")
        _confirm_delete(service)
        events = service.list_events()
        if not events:
            st.info("No events yet. Add your first event above.")
        for saved in events:
            _event_card(saved)
    except EventStorageError as error:
        st.error(str(error))
