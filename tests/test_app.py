"""Smoke-test the Streamlit screen without touching the user's database."""

from pathlib import Path

from pytest import MonkeyPatch
from streamlit.testing.v1 import AppTest

from src.database import db


def test_app_displays_database_status(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    initialize = db.initialize_database
    monkeypatch.setattr(
        db, "initialize_database", lambda: initialize(tmp_path / "planlayer.db")
    )
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run()
    assert not app.exception
    assert app.title[0].value == "PlanLayer"
    assert "Database connected" in app.success[0].value
    app.run()
    assert not app.exception
    assert len(app.success) == 1


def test_app_reports_initialization_failure(monkeypatch: MonkeyPatch) -> None:
    def fail() -> None:
        raise PermissionError("Test-only failure")

    monkeypatch.setattr(db, "initialize_database", fail)
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run()
    assert not app.exception
    assert "Database unavailable" in app.error[0].value
