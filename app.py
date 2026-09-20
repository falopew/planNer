"""Minimal Streamlit entry point for the project foundation."""

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from src.database.db import check_database_health, initialize_database


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
    finally:
        engine.dispose()

    st.caption(
        "Milestone 0: project foundation. Planning features are not implemented yet."
    )


if __name__ == "__main__":
    main()
