# PlanLayer

A personal calendar and life-planning portfolio project. It distinguishes Fixed Events and
Reminders in daily/weekly agendas. Flexible Tasks and explainable scheduling
remain future milestones. No LLM/AI functionality is included.

## Current status

Milestone 4 — Recurrence Engine: shared repeating Events and Reminders, expanded
virtually into Today, Tomorrow, selected Day and Monday–Sunday Week agendas.
One-time CRUD and confirmed deletion remain available. Existing databases upgrade
in place without deleting data.
SQLite initialization, health checks and all foundation behavior remain available.
Tasks, conflict detection, scheduling and recommendations
are **not implemented**.

## Architecture

```text
app.py                  Streamlit presentation entry point
src/ui/events.py        Single create/edit form, event cards and delete confirmation
src/ui/reminders.py     Reminder form and bell-labelled single-time cards
src/ui/schedule.py      Mixed CRUD list preserving item types
src/ui/calendar.py      Read-only Today/Day/Week agendas and navigation
src/ui/categories.py    Shared suggested category strings
src/__init__.py         Application package
src/database/db.py      SQLAlchemy engine, SQLite initialization and health check
src/database/migrations.py  Idempotent additive recurrence-column upgrades
src/database/models.py  SQLAlchemy events/reminders tables and constraints
src/database/repositories.py  Transactional event CRUD and overlap queries
src/database/reminder_repository.py  Independent reminder CRUD and timestamp queries
src/models/event.py     Plain EventInput and saved Event dataclasses
src/models/reminder.py  Separate ReminderInput and saved Reminder dataclasses
src/models/recurrence.py  Shared recurrence settings and readable validation errors
src/services/event_service.py  Input validation and safe application operations
src/services/reminder_service.py  Reminder validation and safe operations
src/services/validation.py  Small shared title/text/local-datetime rules
src/services/schedule_service.py  Combined range/day/week queries (not a scheduling engine)
src/engine/recurrence.py  Strict RRULE builder/parser and bounded occurrence starts
src/ui/recurrence.py     Shared structured repeat controls
src/utils/time_utils.py  Local midnight bounds and Monday-based weeks
tests/test_database.py  Isolated SQLite tests
tests/test_app.py       Streamlit success, rerun and failure smoke tests
tests/test_events.py    Validation, CRUD, range and fresh-process persistence tests
tests/test_event_ui.py  Form workflows, fresh UI session and safe errors
tests/test_reminders.py  Reminder CRUD, boundaries, coexistence and schema upgrade
tests/test_reminder_ui.py  Reminder forms and mixed schedule interactions
tests/test_schedule.py  Ordering, day/week boundaries, overlap and no mutation
tests/test_calendar_ui.py  Today/day/week navigation, rendering and safe errors
tests/test_recurrence.py  Pure patterns, boundaries, invalid rules and fast-forwarding
tests/test_recurrence_storage.py  Real M3 upgrade, persistence and service validation
tests/test_recurrence_schedule.py  Virtual identity, overlap, no writes and query count
tests/test_recurrence_ui.py  Shared repeat controls and whole-series workflows
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

## Calendar behavior

Navigation is **Today → Calendar (Day / Week) → Events / Add Item** via the sidebar.
Today is the default; Tomorrow opens tomorrow in the same Day view. Day offers a
picker and Previous Day / Today / Next Day. Week accepts any date in the desired
week and offers Previous Week / Current Week / Next Week. Seven stacked agendas
keep entries readable; empty days remain visible. Calendar pages have no edit controls.

Calendar UI → ScheduleService → EventService / ReminderService → repositories → SQLite.
`get_schedule_between(start, end)` combines existing bounded queries;
`get_day_schedule(date)` uses local midnight up to (excluding) next midnight.
`get_week_schedule(date)` normalizes to Monday and returns seven ordered date/list
pairs. It fetches and expands once per week, then groups by day in the service.
There are four SELECTs per range/week: two ordinary range queries and two series
candidate queries, independent of the number of series. No per-item DB queries.
Existing Event/Reminder dataclasses retain their types; virtual copies keep the
source ID. Their identity is (type, source ID, occurrence start), never ID alone.

Weeks span Monday 00:00 through next Monday 00:00, excluding the latter. Events
use overlap semantics; reminders use timestamp inclusion. Overnight events appear
once on each overlapping day with their full original date/time endpoints. Order
uses the displayed occurrence start or reminder time, then Event before Reminder, then
ID within type. IDs and audit timestamps are never shown in calendar agendas.
Reminders use a bell, one time and no bordered duration block. Navigating does not
write item records. All dates/times remain local naive values.

## Recurrence (Milestone 4)

Both editors offer Does not repeat, Daily, Weekdays (Monday–Friday), Weekly,
Custom weekly, Monthly and Custom interval (every N days/weeks/months).
Custom weekly supports selected weekdays and a positive week interval.
Choose Ends → Never or On date. Only Create/Save persists changes; repeat-control
reruns retain the current editor draft. Calendar remains read-only.

Rules are built/validated by a shared pure engine, not assembled in UI code.
They are nullable TEXT on each base row. NULL means one-time. Examples:

```text
FREQ=DAILY;INTERVAL=1
FREQ=WEEKLY;INTERVAL=1
FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE,FR
FREQ=MONTHLY;INTERVAL=3
FREQ=WEEKLY;INTERVAL=1;BYDAY=MO;UNTIL=20261130T235959
```

The base datetime is DTSTART; it is not duplicated in the string. Weekly rules
without BYDAY follow that datetime's weekday. Weeks are Monday-based. End dates
are inclusive for occurrence starts; an Event may finish after that date.
UNTIL uses local 23:59:59; the engine preserves fractional seconds from the base.
The parser accepts only the documented subset, not arbitrary RRULE features or
UTC/end-time variants. Invalid rules are rejected before persistence.

The shared dateutil engine generates starts only within a finite requested range.
It skips complete old daily/weekly/monthly cycles while preserving their anchor
phase; it does not enumerate years of old occurrences for a one-week request.
No start precedes DTSTART. Monthly recurrence keeps the original day: January 31
skips February rather than becoming February 28, following
[dateutil's documented behavior](https://dateutil.readthedocs.io/en/stable/rrule.html).

ScheduleService substitutes generated occurrences for each recurring base row,
preventing a duplicate first occurrence. Event copies preserve the original
duration; expansion looks backwards by that duration and checks strict overlap.
Reminder copies use one timestamp only. No occurrences are written to SQLite.
List/CRUD operations still return stored base items, not expanded series.

Editing recurrence affects the entire series. Does not repeat saves NULL and
leaves the base item at its original stored datetime. Deleting the base removes
all virtual occurrences; there are no individual exceptions. Event occurrences
whose end would exceed Python's year-9999 limit are omitted.

## Installation (Python 3.12+)

From PowerShell on Windows:

```powershell
git clone https://github.com/falopew/planNer.git
cd planNer
git fetch origin
git switch milestone-4-recurrence-engine
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

Open http://localhost:8501. Today opens by default. Use Calendar for Day/Week
navigation. Open Events / Add Item and choose Fixed Event or Reminder with the selector. A reminder needs an explicit time selection. Both types appear in the
current schedule. Edit selects the appropriate form; cancellation abandons changes. Delete
requires confirmation. Stop the server with Ctrl+C.

Startup creates `data/planlayer.db` if missing; the default path is anchored
to the repository, independent of the terminal working directory. Existing
data is preserved. SQLite foreign keys are enabled on every connection.
Initialization creates missing `events` and `reminders` tables via SQLAlchemy
`create_all`, including adding reminders to an existing Milestone 1 database.
After `create_all`, `database/migrations.py` inspects both tables and adds a
missing `recurrence_rule TEXT` column. Existing rows get NULL and remain one-time.
The upgrade acquires a SQLite write lock before inspection and is idempotent.
It never drops tables/data. Back up important databases before upgrading.
This lightweight additive migration mechanism is documented technical debt:
there is no Alembic/version ledger, and arbitrary schema changes need an explicit
future migration. `create_all` alone does not update existing columns. Both item types survive a full app restart
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
  conversion, DST disambiguation or UTC storage. This is the Milestones 1–4 policy.
- Reminders are stored in-app information only: no alarms, email, sound,
  OS notifications or background delivery. They have no dismissal/completion state.
- Creation uses one date for start/end. The service accepts overnight intervals;
  editing such a saved interval shows an extra end-date field to preserve it.
- Calendar is an agenda, not an hourly grid. No drag/drop or inline editing.
  The picker excludes seven days at each extreme of Python's date range so
  previous/next navigation and exclusive week ends remain representable.
- Category is a simple string; there is no Category table.
- There is no conflict detection, pagination or multi-user edit
  coordination. Overlapping commitments are allowed and are not flagged yet.
- Recurrence has no yearly rules, COUNT ending, positional weekdays, holidays,
  per-occurrence editing/deletion, exceptions, timezone conversion or DST support.
- Database health means a query succeeds, not a full integrity/schema audit.

## Manual verification

1. Start the app and verify a successful database status and the friendly empty state.
2. Open Events / Add Item. Create Football Training, 25 Sep 2026, 19:00–21:00, category Sport; add description/location.
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

14. Open Today: verify today's event intervals and bell-labelled reminders, including
    a reminder inside an event. Tomorrow must open tomorrow's Day view.
15. In Calendar, pick a date and use Previous Day / Today / Next Day. Check an empty day.
16. Switch to Week. Pick a Wednesday: the agenda must start Monday and end Sunday.
    Use Previous Week / Current Week / Next Week and check the seven day headings.
17. Return to Events / Add Item after browsing; titles/times/counts must be unchanged.
    Verify editing and confirmed deletion still work for both types.

18. Create a daily Event and a weekly Reminder; inspect their future Day/Week entries.
    The base date must not show a duplicate, and database row counts must not grow.
19. Try custom Monday/Wednesday/Friday and every 2 days/weeks or 3 months.
    Set an inclusive end date; check the final matching day and the next one.
20. Edit a series, remove recurrence, then restore and delete it. Future occurrences
    should reflect each change. Cancellation must leave saved data unchanged.
21. On a backup copy of an M3 database, start the new app twice: existing Events and
    Reminders must remain, with no recurrence until explicitly configured.

Development is on `milestone-4-recurrence-engine`; review/test its Pull Request before
merging into `main`. No future product milestones are part of this change.

Read [AGENTS.md](AGENTS.md) for development rules and
[the product specification](docs/PRODUCT_SPEC.md) for the planned roadmap.
