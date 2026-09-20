"""Exercise initialization against isolated temporary SQLite databases."""

from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from src.database.db import check_database_health, initialize_database


def test_initialization_creates_database_and_enables_foreign_keys(
    tmp_path: Path,
) -> None:
    path = tmp_path / "nested" / "planlayer.db"
    engine = initialize_database(path)
    try:
        assert path.is_file()
        assert check_database_health(engine)
        with engine.connect() as connection:
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
            assert inspect(connection).get_table_names() == ["events", "reminders"]
        engine.dispose()
        with engine.connect() as connection:
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
    finally:
        engine.dispose()


def test_reinitialization_preserves_existing_data(tmp_path: Path) -> None:
    path = tmp_path / "planlayer.db"
    engine = initialize_database(path)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE probe (value INTEGER)"))
            connection.execute(text("INSERT INTO probe VALUES (42)"))
    finally:
        engine.dispose()

    engine = initialize_database(path)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT value FROM probe")) == 42
    finally:
        engine.dispose()


def test_health_check_returns_false_for_unavailable_database(tmp_path: Path) -> None:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'missing' / 'db.sqlite').as_posix()}"
    )
    try:
        assert check_database_health(engine) is False
    finally:
        engine.dispose()
