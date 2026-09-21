# PlanLayer product specification

## Status and purpose

PlanLayer is a smart personal calendar and life-planning application built as
a university portfolio project. The repository name remains `planNer`.
Milestone 0 supplies packaging, SQLite initialization/health checks and tests.
Milestone 1 adds persistent Fixed Event creation, editing, deletion, listing
and range queries. Milestone 2 adds separate persistent Reminders and a mixed
chronological display. Flexible Tasks, calendars and engines remain planned.

Milestones 1–2 use local naive datetimes, superseding the original
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
created_at and updated_at. Titles are trimmed and limited to 200 characters;
blank categories default to Other. Category is a string, not a separate table.
Edits preserve id/created_at and refresh updated_at. All times are local naive.
The creation form uses one selected date; the service can store any valid
interval, including overnight events. Overlaps are allowed, but conflict
detection/reporting is NOT implemented in Milestone 1.

Recurring event definitions generate virtual occurrences for the visible
window. Occurrences behave like ordinary events for occupancy and conflict
detection. A stable occurrence identity combines the series ID and occurrence
start instant. The first recurrence milestone supports daily and weekly
patterns with an optional count or end date. An unbounded series is allowed
only with bounded expansion queries. Single-occurrence edits, exclusions and
advanced recurrence patterns are deferred.

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
reminder_datetime, category, created_at and updated_at. It has NO start/end,
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
shared validation helpers, before persistence. No recurrence or notifications
are implemented; dismissal/completion is also deferred.

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
    models.py
    repositories.py
    reminder_repository.py
  models/
    __init__.py
    event.py
    reminder.py
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
    categories.py
  engine/
    __init__.py
  utils/
    __init__.py
tests/
data/
assets/
docs/PRODUCT_SPEC.md
AGENTS.md
```

This requested layout supersedes the earlier `src/planlayer` proposal.
`app.py` owns presentation, `services` orchestration, `engine` pure domain
algorithms, and `database` persistence. `models` contains plain event dataclasses;
`ui` contains forms/cards, and `utils` remains a placeholder. The default local
SQLite path is `data/planlayer.db`; database files are never tracked by Git.
The implemented flow is UI → EventService → EventRepository → SQLAlchemy → SQLite.
The Reminder flow independently uses ReminderService and ReminderRepository.
A user action enters a service; the service loads data through persistence,
passes plain typed values to domain functions, and returns results to the UI.
Accepted changes are saved in a transaction. Use concrete, small modules
rather than a generic repository framework or dependency-injection container.

SQLAlchemy owns database mapping. Domain dataclasses remain independent of
ORM models. pandas prepares report tables; Plotly renders charts.
python-dateutil remains an installed dependency for future recurrence work;
no recurrence or timezone handling is implemented now.

## Temporal and interval rules

- Use half-open intervals `[start, end)`: 10:00–11:00 and 11:00–12:00
  are adjacent, not conflicting.
- Two intervals overlap exactly when `a.start < b.end` and
  `b.start < a.end`. Require positive duration.
- Milestones 1–2 store local naive Python datetimes in SQLite DateTime columns.
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
| events (implemented) | ID, title, description, local naive start/end, category, location, local naive creation/update timestamps |
| recurring_event_series | ID, title, notes, local start, IANA timezone, positive elapsed duration, recurrence rule and timestamps |
| flexible_tasks | ID, title, notes, UTC deadline, estimated minutes, active/completed status, completion timestamp and timestamps |
| scheduled_task_blocks | ID, unique task foreign key, UTC start/end and timestamps |
| reminders (implemented) | ID, title, description, local naive reminder_datetime, category, local naive created_at/updated_at; no end or duration |
| user_preferences | One local user's timezone, week start, planning/sleep/meal settings and load threshold |

Generated occurrences are not database rows in the initial design.
Only `events` and `reminders` are implemented. UTC/timezone fields on other conceptual
tables are future proposals, not current runtime behavior.
Represent preferences with a small validated schema; detailed window storage
will be chosen when that milestone is implemented.

Enforce positive durations, valid time ordering and foreign keys. Add indexes
for event times, deadlines and reminder timestamps as needed by actual queries.
A task deletion deletes its linked block within the same transaction.
Deleting a recurrence definition removes its virtual occurrences; confirmation
belongs in the future UI because it affects an entire series.

Enable SQLite foreign-key enforcement for every connection. Repository writes
commit on success and roll back on failure, with a new session per operation.
Initialization uses SQLAlchemy `create_all` to add missing events/reminders tables without
discarding existing data. No Alembic or migration framework is introduced.
`create_all` cannot migrate existing columns; later schema changes need an
explicit migration plan.
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
4. **Milestone 2 — Reminder Layer (current):** independent reminder CRUD,
   local naive timestamps, half-open timestamp range queries, a mixed chronological
   display and confirmed deletion. No recurrence, notifications or occupied time.
   Verify event coexistence, identical timestamps, database upgrades, persistence
   and all existing event tests. Daily/weekly calendar views remain future work.
5. **Recurring events:** daily/weekly series and bounded expansion.
   Verify overnight overlap, termination limits and DST policy.
6. **Calendar analysis:** conflict detection, merged busy intervals, free gaps
   and daily load. Verify adjacency, containment, cross-day clipping,
   zero capacity and no double-counting.
7. **Preferences and recommendations:** configurable planning/sleep/meal
   windows and deterministic suggestions. Verify impossible recommendations
   are explained and suggestions do not mutate occupancy.
8. **Flexible task scheduling:** proposals, explicit acceptance, unscheduling
   and collision reporting for accepted blocks. Verify deadline boundaries,
   tie-breaking, occupied gaps and insufficient contiguous capacity.
9. **Weekly analytics and portfolio polish:** pandas/Plotly reporting,
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
implemented together with the Reminder Layer. Scheduling engines and other product
milestones remain unimplemented.
