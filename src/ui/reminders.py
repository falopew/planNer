"""Reminder forms and lightweight point-in-time cards."""

from dataclasses import replace
from datetime import date, datetime

import streamlit as st

from src.models.recurrence import RecurrenceValidationError
from src.models.reminder import Reminder, ReminderInput
from src.services.reminder_service import (
    ReminderService,
    ReminderStorageError,
    ReminderValidationError,
)
from src.ui.categories import CATEGORIES
from src.ui.recurrence import render_recurrence_controls, rule_from_controls


def _finish(message: str) -> None:
    st.session_state.pop("editing_reminder_id", None)
    st.session_state.pop("delete_reminder_id", None)
    st.session_state["reminder_notice"] = message
    st.session_state["reminder_form_version"] = (
        st.session_state.get("reminder_form_version", 0) + 1
    )
    st.rerun()


def _form(service: ReminderService, reminder: Reminder | None) -> None:
    st.subheader(f"Edit reminder: {reminder.title}" if reminder else "Add a Reminder")
    st.caption(
        "One moment to remember. Reserves no calendar time; no notification is sent."
    )
    if reminder and st.button("Cancel reminder editing"):
        _finish("Reminder editing cancelled.")
    version = st.session_state.get("reminder_form_version", 0)
    categories = list(CATEGORIES)
    if reminder and reminder.category not in categories:
        categories.append(reminder.category)
    form_key = f"reminder_form_{reminder.id if reminder else 'new'}_{version}"
    with st.container():
        title = st.text_input(
            "Title",
            value=reminder.title if reminder else "",
            max_chars=200,
            key=f"{form_key}_title",
        )
        description = st.text_area(
            "Description",
            value=reminder.description if reminder else "",
            key=f"{form_key}_description",
        )
        day = st.date_input(
            "Date",
            value=reminder.reminder_datetime.date() if reminder else date.today(),
            key=f"{form_key}_date",
        )
        moment = st.time_input(
            "Time",
            value=reminder.reminder_datetime.time() if reminder else None,
            key=f"{form_key}_time",
        )
        category = st.selectbox(
            "Category",
            categories,
            index=categories.index(reminder.category if reminder else "Other"),
            key=f"{form_key}_category",
        )
        recurrence = render_recurrence_controls(
            form_key,
            reminder.recurrence_rule if reminder else None,
            reminder.reminder_datetime if reminder else None,
        )
        if reminder and reminder.recurrence_rule:
            st.caption("Editing recurrence changes the entire series.")
        submitted = st.button(
            "Save reminder changes" if reminder else "Create reminder",
            key=f"{form_key}_save",
        )
    if not submitted:
        return
    data = ReminderInput(
        title=title,
        description=description,
        category=category,
        reminder_datetime=datetime.combine(day, moment)
        if day is not None and moment is not None
        else None,
    )
    try:
        data = replace(
            data, recurrence_rule=rule_from_controls(recurrence, data.reminder_datetime)
        )
        if reminder:
            saved = service.update_reminder(reminder.id, data)
            message = (
                "Reminder updated." if saved else "That reminder no longer exists."
            )
        else:
            service.create_reminder(data)
            message = "Reminder created."
    except (
        ReminderValidationError,
        ReminderStorageError,
        RecurrenceValidationError,
    ) as error:
        st.error(str(error))
        return
    _finish(message)


def _confirm_delete(service: ReminderService) -> None:
    reminder_id = st.session_state.get("delete_reminder_id")
    if reminder_id is None:
        return
    reminder = service.get_reminder(reminder_id)
    if reminder is None:
        st.session_state.pop("delete_reminder_id", None)
        st.info("That reminder no longer exists.")
        return
    st.warning(f'Delete reminder "{reminder.title}"? This cannot be undone.')
    if reminder.recurrence_rule:
        st.warning("This will delete the recurring series and all its occurrences.")
    if st.button("Confirm reminder deletion", key=f"confirm_reminder_{reminder.id}"):
        deleted = service.delete_reminder(reminder.id)
        _finish("Reminder deleted." if deleted else "That reminder no longer exists.")
    if st.button("Cancel reminder deletion"):
        st.session_state.pop("delete_reminder_id", None)
        st.rerun()


def _select_reminder(reminder_id: int, action: str) -> None:
    st.session_state["item_type"] = "Reminder"
    st.session_state[f"{action}_reminder_id"] = reminder_id
    if action == "editing":
        st.session_state.pop("delete_reminder_id", None)


def render_reminder_card(reminder: Reminder) -> None:
    with st.container(border=False):
        st.subheader(f"🔔 {reminder.title}")
        st.write(f"{reminder.reminder_datetime:%d %b %Y, %H:%M}")
        st.caption(f"Reminder · {reminder.category} · No occupied time")
        if reminder.recurrence_rule:
            st.caption("Repeating series · edit/delete affects all occurrences")
        if reminder.description:
            st.write(reminder.description)
        st.button(
            "Edit reminder",
            key=f"edit_reminder_{reminder.id}",
            on_click=_select_reminder,
            args=(reminder.id, "editing"),
        )
        st.button(
            "Delete reminder",
            key=f"delete_reminder_{reminder.id}",
            on_click=_select_reminder,
            args=(reminder.id, "delete"),
        )
        st.divider()


def render_reminder_editor(service: ReminderService) -> None:
    if notice := st.session_state.pop("reminder_notice", None):
        st.success(notice)
    try:
        editing_id = st.session_state.get("editing_reminder_id")
        reminder = service.get_reminder(editing_id) if editing_id is not None else None
        if editing_id is not None and reminder is None:
            st.session_state.pop("editing_reminder_id", None)
            st.info("That reminder no longer exists.")
        _form(service, reminder)
        _confirm_delete(service)
    except (ReminderStorageError, RecurrenceValidationError) as error:
        st.error(str(error))
