# PlanLayer

A personal calendar and life-planning portfolio project. Future milestones
will distinguish Fixed Events, Flexible Tasks and Reminders and add calendar
views and explainable scheduling. No LLM/AI functionality is included.

## Current status

Milestone 2 — Reminder Layer: persistent Fixed Events and Reminders with creation,
editing, confirmed deletion, chronological display, range queries and validation.
SQLite initialization, health checks and all foundation behavior remain available.
Tasks, conflict detection, calendars, scheduling and recommendations
are **not implemented**.

## Architecture

```text
app.py                  Streamlit presentation entry point
src/ui/events.py        Single create/edit form, event cards and delete confirmation
src/ui/reminders.py     Reminder form and bell-labelled single-time cards
src/ui/schedule.py      Mixed chronological display preserving item types
src/ui/categories.py    Shared suggested category strings
src/__init__.py         Application package
src/database/db.py      SQLAlchemy engine, SQLite initialization and health check
src/database/models.py  SQLAlchemy events table and constraints
src/database/repositories.py  Transactional event CRUD and overlap queries
src/database/reminder_repository.py  Independent reminder CRUD and timestamp queries
src/models/event.py     Plain EventInput and saved Event dataclasses
src/models/reminder.py  Separate ReminderInput and saved Reminder dataclasses
src/services/event_service.py  Input validation and safe application operations
src/services/reminder_service.py  Reminder validation and safe operations
src/services/validation.py  Small shared title/text/local-datetime rules
src/services/schedule_service.py  Typed display ordering (not a scheduling engine)
src/engine/             Reserved for pure domain/scheduling algorithms
src/utils/              Reserved for small shared helpers
tests/test_database.py  Isolated SQLite tests
tests/test_app.py       Streamlit success, rerun and failure smoke tests
tests/test_events.py    Validation, CRUD, range and fresh-process persistence tests
tests/test_event_ui.py  Form workflows, fresh UI session and safe errors
tests/test_reminders.py  Reminder CRUD, boundaries, coexistence and schema upgrade
tests/test_reminder_ui.py  Reminder forms and mixed schedule interactions
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

Reminder data flows through Streamlit → ReminderService → ReminderRepository →
SQLAlchemy → SQLite. Shared title/text/datetime checks live in `validation.py`;
ReminderService applies them before writes and converts database failures into
safe messages. Titles are required, trimmed and limited to 200 characters;
blank categories become Other and descriptions may be empty. A local naive
reminder datetime is required. Edit preserves id/created_at and refreshes updated_at.

**A Fixed Event occupies its start/end interval; a Reminder occupies no time.**
The `reminders` table has only one scheduling timestamp, with no end or duration.
Reminder operations never create or change event rows. Event queries return only
events. `get_reminders_between(start, end)` uses
`start <= reminder_datetime < end`, including the start and excluding the end.
Same-time reminders and reminders inside an event are valid.

The current schedule combines typed records for display only, ordered by event
start/reminder timestamp. Ties show events first, then reminders, with ID as a
stable tie-breaker within each type. Reminder entries show a bell, one time and
“No occupied time”; event cards retain their start/end times. Busy events never
hide reminders. No occupancy, conflict, gap or load calculation is implemented.

The literal `src` package follows the requested foundation layout; it is not
the conventional `src/planlayer` packaging layout. Future algorithms will be
added only in their requested milestones.

## Installation (Python 3.12+)

From PowerShell on Windows:

```powershell
git clone https://github.com/falopew/planNer.git
cd planNer
git fetch origin
git switch milestone-2-reminders
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

Open http://localhost:8501. Choose Fixed Event or Reminder with the Add item
selector. A reminder needs an explicit time selection. Both types appear in the
current schedule. Edit selects the appropriate form; cancellation abandons changes. Delete
requires confirmation. Stop the server with Ctrl+C.

Startup creates `data/planlayer.db` if missing; the default path is anchored
to the repository, independent of the terminal working directory. Existing
data is preserved. SQLite foreign keys are enabled on every connection.
Initialization creates missing `events` and `reminders` tables via SQLAlchemy
`create_all`, including adding reminders to an existing Milestone 1 database.
It never drops existing tables/data. No migration framework is added, and
`create_all` does not update existing columns. Both item types survive a full app restart
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

- All event, reminder and audit datetimes are local naive values. No timezone
  conversion, DST disambiguation or UTC storage. This is the Milestones 1–2 policy.
- Reminders are stored in-app information only: no alarms, email, sound,
  OS notifications or background delivery. They do not recur or have a dismissal state.
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
10. Select Reminder and create Take medication, 22 Sep 2026, 11:00, category Health.
11. Create a 10:00–12:00 event on the same date and another reminder at 11:00.
    Verify all three appear chronologically, without conflict warnings.
12. Edit a reminder's title/time, cancel an edit, cancel deletion, then confirm it.
    Verify these actions do not change any event.
13. Restart Streamlit and verify remaining reminders persist. Test blank titles
    and a missing reminder date/time for readable validation messages.

Development is on `milestone-2-reminders`; review/test its Pull Request before
merging into `main`. No future product milestones are part of this change.

Read [AGENTS.md](AGENTS.md) for development rules and
[the product specification](docs/PRODUCT_SPEC.md) for the planned roadmap.
