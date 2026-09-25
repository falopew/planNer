"""Initialize local SQLite and the implemented schema without deleting data."""

import sqlite3
from pathlib import Path

from sqlalchemy import URL, Engine, create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError

from src.database.migrations import upgrade_schema
from src.database.models import Base

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "planlayer.db"


def _enable_foreign_keys(
    connection: sqlite3.Connection, connection_record: object
) -> None:
    """Apply foreign-key enforcement to every new DBAPI connection."""
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def initialize_database(database_path: Path = DEFAULT_DATABASE_PATH) -> Engine:
    """Create the parent folder and open SQLite; preserve any existing data.

    The caller owns the returned engine and should dispose it when finished.
    Missing tables are created; existing tables/data are never recreated.
    Explicit additive upgrades handle recurrence columns on existing tables.
    """
    database_path = database_path.resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(URL.create("sqlite+pysqlite", database=str(database_path)))
    event.listen(engine, "connect", _enable_foreign_keys)
    try:
        Base.metadata.create_all(engine)
        upgrade_schema(engine)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        engine.dispose()
        raise
    return engine


def check_database_health(engine: Engine) -> bool:
    """Return whether a SQL query succeeds (not a schema or integrity audit)."""
    try:
        with engine.connect() as connection:
            return connection.scalar(text("SELECT 1")) == 1
    except SQLAlchemyError:
        return False
