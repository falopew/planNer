# PlanLayer product specification

## Status and purpose

PlanLayer is a smart personal calendar and life-planning application built as
a university portfolio project. The repository name remains `planNer`.
Milestone 0 supplies packaging, SQLite initialization/health checks and tests.
Milestone 1 adds persistent Fixed Event creation, editing, deletion, listing
and range queries. Milestone 2 adds separate persistent Reminders and a mixed
chronological display. Milestone 3 adds Today/Tomorrow, selected Day and Week
agendas. Milestone 4 adds shared recurrence for Events and Reminders, virtual
calendar occurrences and additive schema upgrades. Flexible Tasks and other
scheduling engines remain planned.

Milestones 1–4 use local naive datetimes, superseding the original
timezone-aware/UTC proposal. No conversion or timezone libraries are introduced.

The product helps a person distinguish commitments, work that still needs
time, and lightweight reminders. It should answer: What is fixed today?
What time is free? Can my tasks fit before their deadlines? How busy is my week?

The initial target is one person using a local Streamlit application with a
local SQLite database. Multi-user accounts, cloud synchronization, external
calendar integrations, push/email notifications, and LLM/AI features are out
of scope unless explicitly requested. "Smart" means transparent rules and
deterministic algorithms.

## Core item types

| Item | Required timing | Occupies time | Scheduling behavior |
| --- | --- | --- | --- |
| Fixed Event | Start and end datetime | Yes | Can overlap other Fixed Events; overlap is reported |
| Flexible Task | Deadline and positive estimated duration | No, until explicitly scheduled | Can receive a linked scheduled block in available time |
| Reminder | Reminder datetime | Never | Appears in a separate layer; never creates conflicts |

Planned items have an identifier, title, optional notes, and creation/update
timestamps. Titles must not be blank.

### Fixed Events

A Fixed Event represents an existing commitment, such as a lecture or meeting.
Its end must be later than its start. The implemented `events` table stores
id, title, description, start_datetime, end_datetime, category, location,
created_at, updated_at and nullable recurrence_rule. Titles are trimmed and limited to 200 characters;
blank categories default to Other. Category is a string, not a separate table.
Edits preserve id/created_at and refresh updated_at. All times are local naive.
The creation form uses one selected date; the service can store any valid
interval, including overnight events. Overlaps are allowed, but conflict
detection/reporting is NOT implemented in Milestone 1.

Recurring base items generate virtual occurrences for a finite visible window.
A stable occurrence identity combines item type, source ID and occurrence start.
Daily, weekdays, weekly/selected weekdays, monthly, positive intervals and an
optional inclusive end date are supported. COUNT, yearly recurrence, exceptions,
timezones and per-occurrence edits are deferred. No conflict detection is implemented.

### Flexible Tasks

A Flexible Task has a deadline and estimated duration in positive integer
minutes. Initially it has no scheduled start or end. A past deadline is
allowed and makes an unfinished task overdue.

A task can be active or completed. Scheduling is represented independently by
a linked Scheduled Task Block, not by changing its type to Fixed Event.
Initially each task has at most one block, and its block duration equals its
estimate. Task splitting and partial completion are deferred.

A proposed placement must end at or before the deadline, fit wholly inside
allowed free time and avoid occupied intervals. Scheduling suggestions do
not change the calendar until accepted. Accepted blocks occupy time and are
included in occupancy, free-gap detection and planned load. If a later event
overlaps a task block, report a collision and offer replanning; do not silently
move either item. Unscheduling removes the placement, not the task.
Completion does not automatically delete its recorded block.

### Reminders

A Reminder is an independent record containing id, title, description,
reminder_datetime, category, created_at, updated_at and nullable recurrence_rule.
It has NO start/end,
duration or active/dismissed fields in Milestone 2. Titles are trimmed, nonblank
and at most 200 characters; blank category defaults to Other. Description is
optional. All timestamps are local naive values. Edits preserve id/created_at
and refresh updated_at. Deletion requires UI confirmation.

Even inside an event or at another reminder's exact timestamp, it remains
valid and visible. It never occupies time, creates conflicts, blocks scheduling,
subtracts free time or increases load. It is not a zero-duration Fixed Event.
The reminder repository queries only the reminders table; EventRepository
continues to return events only.

The UI offers a Fixed Event/Reminder selector, a single active editing form and
a combined chronological list. Reminder cards use a bell and one timestamp;
event cards retain start/end intervals. ScheduleService combines typed records
only for display, with events before reminders at equal timestamps and ID as
a stable tie-breaker. It performs no occupancy/conflict calculations.

Reminder range selection uses `range_start <= reminder_datetime < range_end`.
Invalid, missing or timezone-aware input is rejected by ReminderService using
shared validation helpers, before persistence. Recurrence shares the Event engine
but generates only reminder instants. Notifications and dismissal/completion are deferred.

The initial reminder experience is in-app display when the app is open.
It does not promise operating-system alarms or delivery while Streamlit is closed.

## Architecture

Use Python 3.12+, Streamlit, SQLite, SQLAlchemy, pandas, Plotly,
python-dateutil, pytest and ruff. Dependency ranges, setuptools packaging, pytest and ruff configuration are
defined in `pyproject.toml`; pytest and ruff belong to the `dev` extra.

| Layer | Responsibility | Must not contain |
| --- | --- | --- |
| UI | Streamlit forms, daily/weekly views, reminder display, charts and feedback | Scheduling decisions, SQL or business rules |
| Services/application | Use cases, validation orchestration, persistence transactions, gathering data for engines | Streamlit rendering or duplicated domain algorithms |
| Domain/scheduling | Typed models and pure interval, recurrence, load and scheduling functions | Database sessions, Streamlit, network access |
| Persistence | SQLAlchemy mappings, SQLite access, bounded queries and session management | UI behavior or scheduling policy |

Current foundation layout:

```text
app.py
src/
  __init__.py
  database/
    __init__.py
    db.py
    migrations.py
    models.py
    repositories.py
    reminder_repository.py
  models/
    __init__.py
    event.py
    reminder.py
    recurrence.py
  services/
    __init__.py
    event_service.py
    reminder_service.py
    schedule_service.py
    validation.py
  ui/
    __init__.py
    events.py
    reminders.py
    schedule.py
    calendar.py
    categories.py
    recurrence.py
  engine/
    __init__.py
    recurrence.py
  utils/
    __init__.py
    time_utils.py
tests/
data/
assets/
docs/PRODUCT_SPEC.md
AGENTS.md
```

This requested layout supersedes the earlier `src/planlayer` proposal.
`app.py` owns presentation, `services` orchestration, `engine` pure domain
algorithms, and `database` persistence. `models` contains plain event dataclasses;
`ui` contains forms/cards and calendar agendas; `utils/time_utils.py` centralizes
local day bounds, Monday normalization and week bounds. The default local
SQLite path is `data/planlayer.db`; database files are never tracked by Git.
The implemented flow is UI → EventService → EventRepository → SQLAlchemy → SQLite.
The Reminder flow independently uses ReminderService and ReminderRepository.
A user action enters a service; the service loads data through persistence,
passes plain typed values to domain functions, and returns results to the UI.
Accepted changes are saved in a transaction. Use concrete, small modules
rather than a generic repository framework or dependency-injection container.

SQLAlchemy owns database mapping. Domain dataclasses remain independent of
ORM models. pandas prepares report tables; Plotly renders charts.
python-dateutil powers the bounded recurrence engine; timezone handling remains deferred.

## Calendar views (Milestone 3)

Today is the default sidebar destination; Tomorrow opens Calendar's Day view.
Calendar offers Day and Week, date selection, previous/next navigation, and
Today/Current Week reset. Events / Add Item retains both existing CRUD workflows.
No placeholder Settings/Analytics pages, calendar editing or grid.

Calendar UI calls only ScheduleService. Its combined bounded query delegates to
EventService and ReminderService. Day uses `[midnight, next midnight)`; Week
normalizes any selected date to Monday and returns an ordered mapping of seven
dates to day schedules. It fetches and expands the week once (four SELECTs), then
groups in the service with shared half-open overlap semantics. Query count does
not grow with the number of series. The week ends at next Monday, excluded.

Existing Event/Reminder dataclasses are the shared typed display representation;
no additional model/table is needed. Copies preserve source IDs; identity is
(type, source ID, occurrence start), never ID alone. Items sort by occurrence start/reminder
instant, then Event before Reminder, then ID within type. An overnight event
appears once per overlapping day with its original endpoints, including dates.
Reminders are lighter, bell-labelled single instants with no duration block.
Category and optional notes/location are visible; IDs/audit times are hidden.
Empty days have explicit messages. Navigation never writes item records.

Calendar remains display/navigation only: recurrence expansion is in the engine
and services. No conflict detection, occupancy calculation, task scheduling,
analytics or notifications. Datetimes stay local naive.

## Shared recurrence engine (Milestone 4)

Persist only nullable `recurrence_rule TEXT` on each base Event/Reminder. NULL is
one-time. The stored datetime acts as DTSTART. There is no separate series table
and no occurrence rows. Existing callers default to non-recurring behavior.

`RecurrencePattern` holds daily/weekly/monthly frequency, positive integer interval,
optional weekdays (Monday=0) and optional end date. A pure shared engine builds,
parses, validates and expands the supported RRULE subset. Examples:
`FREQ=DAILY;INTERVAL=1`, `FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE,FR`,
`FREQ=MONTHLY;INTERVAL=3`. Weekly without BYDAY follows the anchor weekday;
Weekdays is weekly with BYDAY=MO,TU,WE,TH,FR. Week cycles always start Monday.

End dates are inclusive for starts, encoded as local `UNTIL=YYYYMMDDT235959`.
Fractional seconds from the anchor are preserved. No COUNT, yearly frequency,
ordinal weekdays, exceptions, UTC or arbitrary UNTIL time variants are accepted.
Invalid/malformed/unsupported rules become readable validation errors before writes.
A custom weekly rule requires weekdays; the end date cannot precede the anchor date.

The engine only expands finite requested ranges. It fast-forwards whole cycles
near the lower bound without changing their original phase, then delegates to
dateutil with explicit weekday/month-day defaults. Tests compare results against
dateutil expansion from the original anchor. No start precedes DTSTART. Monthly
31st skips months without day 31; no last-day fallback. Empty engine ranges return
an empty list; ScheduleService retains its existing rejection of nonpositive ranges.

ScheduleService excludes recurring base rows from ordinary range results and
substitutes virtual copies exactly once. Events preserve the base duration;
search starts one duration before the window, then filters by interval overlap.
Reminders only generate points in `[start, end)`. Long/overnight events can appear
on multiple days; occurrences with an unrepresentable end beyond year 9999 are omitted.
Ordering stays timestamp, Event before Reminder, then source ID. CRUD listing
returns base items, never an unbounded list of occurrences. Expansion never writes.

Both editors share structured repeat controls and explicit Create/Save buttons.
The controls rerun interactively with keyed draft fields rather than batched
Streamlit forms, so custom options appear immediately without writing data.
Editing/deleting affects the entire series; removal of recurrence saves NULL,
leaving the base item at its stored datetime. Calendar stays read-only.

## Temporal and interval rules

- Use half-open intervals `[start, end)`: 10:00–11:00 and 11:00–12:00
  are adjacent, not conflicting.
- Two intervals overlap exactly when `a.start < b.end` and
  `b.start < a.end`. Require positive duration.
- Milestones 1–4 store local naive Python datetimes in SQLite DateTime columns.
  EventService and ReminderService reject missing, non-datetime and timezone-aware inputs.
  No UTC conversion or timezone preferences are implemented.
- Range queries return complete records overlapping the half-open query range,
  including events that start before it. They do not clip or change stored times.
- Known limitation: local naive times cannot disambiguate daylight-saving
  transitions or represent travel/multiple timezones reliably. System clock
  changes also affect audit timestamps. Timezone support requires a later
  explicit design and migration; do not reinterpret old records silently.
- Future occupancy algorithms may merge/clip intervals, but Milestone 1 only
  queries overlap with a range; it does not detect conflicts between events.

## Planned engines

### Recurrence and conflict detection

Expand only occurrences relevant to a requested date range. Compare occupied
intervals and return the involved item/occurrence IDs and overlap interval.
Classify Fixed Event versus Fixed Event as a commitment conflict and any
overlap involving an accepted task block as a placement collision.
Reminders and unscheduled tasks are excluded entirely.

### Free-gap detection

Build the union of occupied intervals and subtract it from the chosen planning
windows. Return ordered gaps with start, end and duration, optionally filtered
by minimum duration. Accepted task blocks count as busy.
Sleep/planning preferences restrict schedulable windows without masquerading
as Fixed Events. Reminders never participate in subtraction.

### Daily load calculation

Report occupied minutes clipped to the local day, using the union so overlaps
are counted once. Also report planning-window capacity and occupied minutes
inside that capacity. Load percentage equals occupied capacity divided by
capacity, multiplied by 100. Return an unavailable percentage when capacity is
zero rather than dividing by zero.

Show event minutes, scheduled task minutes and outstanding task estimates as
separate measures. Category totals can overlap and must not be presented as
additive to union occupancy. Unscheduled work and reminders do not increase
calendar load. Any overload label uses an explicit user-configurable threshold;
it is not a health assessment.

### Preferences and sleep/meal recommendations

Preferences include timezone, week start, allowed task-planning windows,
sleep window or target, meal windows/durations, and load threshold.
Validate ranges and window consistency. The initial week starts Monday;
timezone selection belongs to a later timezone-support milestone; current
Fixed Events use local naive times without a preference setting.

Recommendations use user preferences and available gaps. They suggest sleep
or meal windows and explain when no suitable gap exists. They never override
commitments or create occupied time automatically. If the user accepts a
recommendation as a reservation, create a Fixed Event through the ordinary
event service. These are personal planning aids, not medical advice.

### Flexible task scheduling

For an explicit finite planning horizon, consider active unscheduled tasks.
Start no earlier than the supplied current time and respect each deadline.
Use earliest deadline first, breaking ties by creation timestamp then task ID.
For each task, choose the earliest remaining gap large enough for its full
duration, then reduce the gap available to subsequent proposals.

Keep accepted placements unchanged. Return suggested blocks and an explicit
reason for every unplaced task, such as expired deadline or insufficient
contiguous capacity. This greedy algorithm is explainable but does not
guarantee an optimal schedule. Before saving accepted suggestions, recheck
current occupancy and deadlines in the service transaction.

### Weekly analytics

Aggregate local-day metrics across the configured week: union occupied time,
daily load, event/task breakdown, free capacity, conflict/collision counts,
task completions and outstanding work. Count each conflict pair once and
define its date attribution explicitly when implemented. Use completion
timestamps for tasks completed during the week.

Analytics describe recorded plans and completion states, not measured time
spent. They are computed on demand, not stored as duplicate summary tables.
Initially there is no historical snapshot/versioning system: editing past
records can change past reports.

## Database concept

Use separate tables to enforce the semantic distinctions without a large
nullable "everything is an item" table.

| Table | Conceptual contents |
| --- | --- |
| events (implemented) | ID, title, description, local naive start/end, category, location, local naive creation/update timestamps, nullable recurrence_rule |
| flexible_tasks | ID, title, notes, UTC deadline, estimated minutes, active/completed status, completion timestamp and timestamps |
| scheduled_task_blocks | ID, unique task foreign key, UTC start/end and timestamps |
| reminders (implemented) | ID, title, description, local naive reminder_datetime, category, local naive created_at/updated_at, nullable recurrence_rule; no end or duration |
| user_preferences | One local user's timezone, week start, planning/sleep/meal settings and load threshold |

Generated occurrences are not database rows in the initial design.
Only `events` and `reminders` are implemented. UTC/timezone fields on other conceptual
tables are future proposals, not current runtime behavior.
Represent preferences with a small validated schema; detailed window storage
will be chosen when that milestone is implemented.

Enforce positive durations, valid time ordering and foreign keys. Add indexes
for event times, deadlines and reminder timestamps as needed by actual queries.
A task deletion deletes its linked block within the same transaction.
Deleting a recurring base removes every virtual occurrence; the current UI
warns explicitly that deletion affects the whole series.

Enable SQLite foreign-key enforcement for every connection. Repository writes
commit on success and roll back on failure, with a new session per operation.
Initialization uses SQLAlchemy `create_all` to add missing events/reminders tables without
discarding existing data. No Alembic or migration framework is introduced.
`create_all` cannot migrate existing columns. After it runs, the isolated
`database/migrations.py` upgrade acquires SQLite's write lock, inspects tables,
and adds missing recurrence columns with ALTER TABLE. Existing rows remain intact
with NULL recurrence. Repeated initialization and new installations are supported.
This is lightweight additive migration debt, not a general schema migration
framework: no version ledger or Alembic. Future changes need explicit migration
steps. Users should back up important databases, never delete them to upgrade.
Local database files must be excluded from version control.

## Development roadmap and acceptance gates

Each milestone requires an explicit implementation request. Dependencies below
describe ordering, not permission to build ahead.

1. **Specification (complete):** AGENTS.md and this product specification.
2. **Milestone 0 — Project Foundation (complete):** packaging/test/lint setup,
   package placeholders, SQLite initialization/health check and minimal UI.
   No domain tables or planning features. Test isolated initialization and reruns.
3. **Milestone 1 — Fixed Events (complete):** validated CRUD, chronological listing,
   half-open range queries, local naive datetimes, persistent SQLite records,
   create/edit form, confirmed deletion and empty state. Tasks/reminders deferred.
   Verify persistence across a fresh process and all foundation checks.
4. **Milestone 2 — Reminder Layer (complete):** independent reminder CRUD,
   local naive timestamps, half-open timestamp range queries, a mixed chronological
   display and confirmed deletion. No recurrence, notifications or occupied time.
   Verify event coexistence, identical timestamps, database upgrades, persistence
   and all existing event tests.
5. **Milestone 3 — Day & Week Calendar Views (complete):** Today/Tomorrow,
   selected-day and Monday–Sunday agendas via ScheduleService, with read-only
   date navigation, deterministic combined ordering and distinct reminder styling.
   Verify midnight boundaries, overnight overlap, empty days, week selection,
   no navigation mutations and all existing CRUD tests.
6. **Milestone 4 — Recurrence Engine (current):** shared Event/Reminder daily,
   weekdays, weekly/selected weekdays, monthly, intervals and inclusive end dates.
   Virtual expansion only; whole-series edit/delete and safe additive upgrades.
   Verify boundaries, overnight duration, no duplicates/materialization, recurrence
   persistence/removal, real M3 upgrade, UI controls and existing regressions.
7. **Calendar analysis:** conflict detection, merged busy intervals, free gaps
   and daily load. Verify adjacency, containment, cross-day clipping,
   zero capacity and no double-counting.
8. **Preferences and recommendations:** configurable planning/sleep/meal
   windows and deterministic suggestions. Verify impossible recommendations
   are explained and suggestions do not mutate occupancy.
9. **Flexible task scheduling:** proposals, explicit acceptance, unscheduling
   and collision reporting for accepted blocks. Verify deadline boundaries,
   tie-breaking, occupied gaps and insufficient contiguous capacity.
10. **Weekly analytics and portfolio polish:** pandas/Plotly reporting,
   documented metric definitions, example walkthrough and interview-ready
   explanation. Verify report aggregates against domain results.

## Quality and scope decisions

Core algorithms require automated pytest tests independent of Streamlit and
SQLite. Persistence/service tests use isolated temporary databases.
Use ruff for linting and formatting once tooling exists. Prefer straightforward
typed functions over unnecessary abstractions.

The first implementation intentionally uses a single local user, unsplit task
placements, a deterministic greedy scheduler, virtual recurrence occurrences,
and in-app reminders. These choices keep the project understandable while
leaving clear extension points. Only the foundation and Fixed Event CRUD are
implemented together with the Reminder Layer, read-only calendar agendas and shared
recurrence. Other scheduling engines and product milestones remain unimplemented.
