"""Small, explicit additive SQLite upgrades; not a general migration framework."""

from sqlalchemy import Engine, inspect


def upgrade_schema(engine: Engine) -> None:
    """Preserve M1–M3 data; missing nullable columns give old rows NULL.

    Acquire SQLite's write lock before inspecting, so simultaneous app startups
    cannot both attempt the same ALTER. Only fixed, internal identifiers are used.
    """
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            for table in ("events", "reminders"):
                columns = {
                    column["name"] for column in inspect(connection).get_columns(table)
                }
                if "recurrence_rule" not in columns:
                    connection.exec_driver_sql(
                        f"ALTER TABLE {table} ADD COLUMN recurrence_rule TEXT"
                    )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
