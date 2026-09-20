# PlanLayer

A personal calendar and life-planning portfolio project. Future milestones
will distinguish Fixed Events, Flexible Tasks and Reminders and add calendar
views and explainable scheduling. No LLM/AI functionality is included.

## Current status

Milestone 1 — Fixed Events: persistent event creation, editing, confirmed
deletion, chronological listing, date/time range queries and basic validation.
SQLite initialization, health checks and all foundation behavior remain available.
Tasks, reminders, conflict detection, calendars, scheduling and recommendations
are **not implemented**.

## Architecture

```text
app.py                  Streamlit presentation entry point
src/ui/events.py        Single create/edit form, event cards and delete confirmation
src/__init__.py         Application package
src/database/db.py      SQLAlchemy engine, SQLite initialization and health check
src/database/models.py  SQLAlchemy events table and constraints
src/database/repositories.py  Transactional event CRUD and overlap queries
src/models/event.py     Plain EventInput and saved Event dataclasses
src/services/event_service.py  Input validation and safe application operations
src/engine/             Reserved for pure domain/scheduling algorithms
src/utils/              Reserved for small shared helpers
tests/test_database.py  Isolated SQLite tests
tests/test_app.py       Streamlit success, rerun and failure smoke tests
tests/test_events.py    Validation, CRUD, range and fresh-process persistence tests
tests/test_event_ui.py  Form workflows, fresh UI session and safe errors
data/                   Local database (ignored by Git)
assets/                 Reserved for visual assets
```

Data flows from Streamlit → Event Service → Event Repository → SQLAlchemy → SQLite.
The service trims text, enforces a nonblank title (up to 200 characters), defaults
blank categories to Other, requires local naive datetimes, and checks end > start.
Validation runs before create/update reaches the repository. Range queries also
validate their interval. Database constraints provide a second check for title,
category and interval integrity. The UI displays safe validation/storage messages.

Repositories use a fresh session per operation. Writes commit on success and roll
back on failure. They return plain dataclasses, so the UI never handles sessions
or ORM records. Editing preserves id/created_at and refreshes updated_at.
Missing reads/updates return None; deleting a missing ID returns False.

`get_events_between(start, end)` returns chronological matches satisfying
`event.start_datetime < end AND event.end_datetime > start`. It includes events
that begin before the range and excludes events merely touching its boundaries.
This is range selection, not event-versus-event conflict detection.

The literal `src` package follows the requested foundation layout; it is not
the conventional `src/planlayer` packaging layout. Future algorithms will be
added only in their requested milestones.

## Installation (Python 3.12+)

From PowerShell on Windows:

```powershell
git clone https://github.com/falopew/planNer.git
cd planNer
git fetch origin
git switch milestone-1-fixed-events
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

On macOS/Linux, after cloning and entering the repository:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
```

The project supports Python 3.12 and newer. Substitute an installed newer
interpreter if needed. Runtime dependencies are Streamlit, SQLAlchemy, pandas,
Plotly and python-dateutil; the `dev` extra adds pytest and ruff.

## Run locally

Run from the repository root on Windows:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

On macOS/Linux:

```bash
.venv/bin/python -m streamlit run app.py
```

Open http://localhost:8501. The screen shows database status and a Fixed Event
form/list. Edit uses the same form; Cancel editing abandons changes. Delete
requires confirmation. Stop the server with Ctrl+C.

Startup creates `data/planlayer.db` if missing; the default path is anchored
to the repository, independent of the terminal working directory. Existing
data is preserved. SQLite foreign keys are enabled on every connection.
Initialization creates the `events` table if missing via SQLAlchemy `create_all`.
It never drops existing tables/data. No migration framework is added, and
`create_all` does not update existing columns. Events survive a full app restart
because committed rows live on disk, not in Streamlit session state.
The health check executes `SELECT 1`; it does not check future schema versions
or prove database integrity. The engine is closed after each page run, keeping
the small foundation simple and safe on Streamlit reruns.

Database files and journal/WAL sidecars are ignored by Git. Only the directory
placeholder is tracked. Use an editable install from the checkout so the
default database remains under the project's `data/` directory.

## Development checks

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
```

On macOS/Linux replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.
Tests use temporary databases and never touch `data/planlayer.db`.

## Known limitations

- All event and audit datetimes are local naive values. No timezone conversion,
  DST disambiguation or UTC storage. This is the explicit Milestone 1 policy.
- Creation uses one date for start/end. The service accepts overnight intervals;
  editing such a saved interval shows an extra end-date field to preserve it.
- Category is a simple string; there is no Category table.
- There is no conflict detection, recurrence, pagination or multi-user edit
  coordination. Overlapping commitments are allowed and are not flagged yet.
- Database health means a query succeeds, not a full integrity/schema audit.

## Manual verification

1. Start the app and verify a successful database status and the friendly empty state.
2. Create Football Training, 25 Sep 2026, 19:00–21:00, category Sport; add description/location.
3. Verify all values appear in the saved event card. Refresh; no duplicate should appear.
4. Submit a blank/whitespace title, equal times, and reversed times; verify clear errors.
5. Edit the event title/time and save. Cancel a second edit and verify no saved changes.
6. Stop Streamlit with Ctrl+C, restart with the same command, and verify the event persists.
7. Add events at 14:00, 09:00 and 11:00 on one day; verify chronological ordering.
8. Click Delete, cancel, then delete again and confirm. Verify it stays deleted after restart.
9. Run `git status --short`; `data/planlayer.db` and SQLite sidecars must not appear.

Development is on `milestone-1-fixed-events`; review/test its Pull Request before
merging into `main`. No future product milestones are part of this change.

Read [AGENTS.md](AGENTS.md) for development rules and
[the product specification](docs/PRODUCT_SPEC.md) for the planned roadmap.
