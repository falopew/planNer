"""Display distinct event intervals and reminder instants in one ordered list."""

import streamlit as st

from src.models.event import Event
from src.models.reminder import Reminder
from src.services.event_service import EventStorageError
from src.services.reminder_service import ReminderStorageError
from src.services.schedule_service import ScheduleService
from src.ui.events import render_event_card
from src.ui.reminders import render_reminder_card


def render_schedule(service: ScheduleService) -> None:
    st.subheader("Current schedule")
    try:
        items = service.list_items()
    except (EventStorageError, ReminderStorageError) as error:
        st.error(str(error))
        return
    if not any(isinstance(item, Event) for item in items):
        st.info("No events yet. Add your first event above.")
    if not any(isinstance(item, Reminder) for item in items):
        st.info("No reminders yet.")
    for item in items:
        if isinstance(item, Event):
            render_event_card(item)
        else:
            render_reminder_card(item)
