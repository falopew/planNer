# PlanLayer product specification

## Status and purpose

PlanLayer is a smart personal calendar and life-planning application built as
a university portfolio project. The repository name remains `planNer`.
This specification describes planned behavior; no application functionality
is implemented in this milestone.

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

All items have an identifier, title, optional notes, and creation/update
timestamps. Titles must not be blank.

### Fixed Events

A Fixed Event represents an existing commitment, such as a lecture or meeting.
Its end must be later than its start. Events may cross midnight.
Overlapping events remain visible; the system reports conflicts rather than
silently deleting, moving or rejecting the real commitments.

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

A Reminder has a reminder datetime and an active/dismissed state. It can be
shown as a marker or list entry in daily/weekly views. Dismissal affects its
presentation only. Even if its timestamp falls inside an event, it must never
generate a scheduling conflict, subtract free time or increase load.

The initial reminder experience is in-app display when the app is open.
It does not promise operating-system alarms or delivery while Streamlit is closed.

## Architecture

Use Python 3.12+, Streamlit, SQLite, SQLAlchemy, pandas, Plotly,
python-dateutil, pytest and ruff. Dependency versions and packaging will be
selected when implementation is requested.

| Layer | Responsibility | Must not contain |
| --- | --- | --- |
| UI | Streamlit forms, daily/weekly views, reminder display, charts and feedback | Scheduling decisions, SQL or business rules |
| Services/application | Use cases, validation orchestration, persistence transactions, gathering data for engines | Streamlit rendering or duplicated domain algorithms |
| Domain/scheduling | Typed models and pure interval, recurrence, load and scheduling functions | Database sessions, Streamlit, network access |
| Persistence | SQLAlchemy mappings, SQLite access, bounded queries and session management | UI behavior or scheduling policy |

Planned source layout:

```text
src/planlayer/
  ui/
  services/
  domain/
  persistence/
tests/
  unit/
  integration/
docs/PRODUCT_SPEC.md
AGENTS.md
```

This is a conceptual layout, not scaffolding to create during this milestone.
A user action enters a service; the service loads data through persistence,
passes plain typed values to domain functions, and returns results to the UI.
Accepted changes are saved in a transaction. Use concrete, small modules
rather than a generic repository framework or dependency-injection container.

SQLAlchemy owns database mapping. Domain dataclasses remain independent of
ORM models. pandas prepares report tables; Plotly renders charts.
python-dateutil supports bounded recurrence expansion, while the standard
library's timezone facilities handle IANA timezone interpretation.

## Temporal and interval rules

- Use half-open intervals `[start, end)`: 10:00–11:00 and 11:00–12:00
  are adjacent, not conflicting.
- Two intervals overlap exactly when `a.start < b.end` and
  `b.start < a.end`. Require positive duration.
- Store one-off instants in UTC through an explicit SQLAlchemy conversion
  convention; SQLite does not supply reliable timezone semantics by itself.
  Restore aware UTC values on reads and reject naive datetimes at boundaries.
- Interpret visible days/weeks in the user's IANA timezone. A local day can
  contain 23 or 25 elapsed hours; do not assume every day is 24 hours.
- Store recurrence local start, timezone and elapsed duration so a weekly
  09:00 commitment stays at 09:00 local time across daylight-saving changes.
- For nonexistent local times during a DST change, request a valid replacement
  for user input and skip that recurring occurrence with a visible warning.
  For ambiguous local times, accept an explicit offset/fold; default recurrence
  expansion to the first occurrence and document that choice in tests.
- Query bounded windows, retain overlapping overnight occurrences, clip to
  the calculation window, then merge busy intervals before measuring duration.
- A preference timezone change changes display, not stored one-off instants
  or the timezone attached to an existing recurring series.

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
timezone must be explicitly selected or confirmed before entering timed items.

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
| fixed_events | ID, title, notes, UTC start/end, creation/update timestamps; one-off commitments |
| recurring_event_series | ID, title, notes, local start, IANA timezone, positive elapsed duration, recurrence rule and timestamps |
| flexible_tasks | ID, title, notes, UTC deadline, estimated minutes, active/completed status, completion timestamp and timestamps |
| scheduled_task_blocks | ID, unique task foreign key, UTC start/end and timestamps |
| reminders | ID, title, notes, UTC reminder time, active/dismissed state and timestamps |
| user_preferences | One local user's timezone, week start, planning/sleep/meal settings and load threshold |

Generated occurrences are not database rows in the initial design.
Represent preferences with a small validated schema; detailed window storage
will be chosen when that milestone is implemented.

Enforce positive durations, valid time ordering and foreign keys. Add indexes
for event times, deadlines and reminder timestamps as needed by actual queries.
A task deletion deletes its linked block within the same transaction.
Deleting a recurrence definition removes its virtual occurrences; confirmation
belongs in the future UI because it affects an entire series.

Enable SQLite foreign-key enforcement for every connection. Use transactions
for multi-record operations. Define and version schema changes when persistence
is introduced; do not silently recreate or discard user databases.
Local database files must be excluded from version control.

## Development roadmap and acceptance gates

Each milestone requires an explicit implementation request. Dependencies below
describe ordering, not permission to build ahead.

1. **Specification (current):** AGENTS.md and this product specification only.
2. **Foundation and core records:** establish packaging/test/lint setup,
   typed models, SQLite persistence and service CRUD for the three core types.
   Verify validation and persistence round trips in temporary databases.
3. **Daily/weekly views and reminder layer:** display local-time events and
   reminders through services. Verify reminders never reserve calendar space
   and Streamlit reruns do not duplicate writes.
4. **Recurring events:** daily/weekly series and bounded expansion.
   Verify overnight overlap, termination limits and DST policy.
5. **Calendar analysis:** conflict detection, merged busy intervals, free gaps
   and daily load. Verify adjacency, containment, cross-day clipping,
   zero capacity and no double-counting.
6. **Preferences and recommendations:** configurable planning/sleep/meal
   windows and deterministic suggestions. Verify impossible recommendations
   are explained and suggestions do not mutate occupancy.
7. **Flexible task scheduling:** proposals, explicit acceptance, unscheduling
   and collision reporting for accepted blocks. Verify deadline boundaries,
   tie-breaking, occupied gaps and insufficient contiguous capacity.
8. **Weekly analytics and portfolio polish:** pandas/Plotly reporting,
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
leaving clear extension points. None of the planned source layout, schema,
engines or milestone functionality is implemented by these documents.
