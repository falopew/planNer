"""Compose the database, event service and Streamlit presentation."""

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from src.database.db import check_database_health, initialize_database
from src.database.reminder_repository import ReminderRepository
from src.database.repositories import EventRepository
from src.services.event_service import EventService
from src.services.reminder_service import ReminderService
from src.services.schedule_service import ScheduleService
from src.ui.calendar import render_calendar, render_today
from src.ui.events import render_event_editor
from src.ui.reminders import render_reminder_editor
from src.ui.schedule import render_schedule


def main() -> None:
    st.set_page_config(page_title="PlanLayer", page_icon="📅")
    st.title("PlanLayer")
    st.write(
        "A personal calendar and life planner for commitments, tasks and reminders."
    )

    try:
        engine = initialize_database()
    except (OSError, SQLAlchemyError):
        st.error("Database unavailable. Check access to the local data directory.")
        return

    try:
        if check_database_health(engine):
            st.success("Database connected — SQLite is ready.")
        else:
            st.error("Database connection check failed.")
            return
        st.caption(
            "Milestone 3: Day & Week Calendar Views. "
            "Times are local, without timezone conversion."
        )
        events = EventService(EventRepository(engine))
        reminders = ReminderService(ReminderRepository(engine))
        schedule = ScheduleService(events, reminders)
        page = st.sidebar.radio(
            "Navigate", ("Today", "Calendar", "Events / Add Item"), key="page"
        )
        if page == "Today":
            render_today(schedule)
            return
        if page == "Calendar":
            render_calendar(schedule)
            return
        item_type = st.radio(
            "Add item", ("Fixed Event", "Reminder"), horizontal=True, key="item_type"
        )
        if item_type == "Fixed Event":
            render_event_editor(events)
        else:
            render_reminder_editor(reminders)
        render_schedule(schedule)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
