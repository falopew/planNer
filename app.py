"""Compose the database, event service and Streamlit presentation."""

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from src.database.db import check_database_health, initialize_database
from src.database.repositories import EventRepository
from src.services.event_service import EventService
from src.ui.events import render_events


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
            "Milestone 1: Fixed Events. Times are local, without timezone conversion."
        )
        render_events(EventService(EventRepository(engine)))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
