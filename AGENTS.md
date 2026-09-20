# PlanLayer development rules

## Project and scope

PlanLayer is a smart personal calendar and life-planning portfolio project.
The GitHub repository is named `planNer`; the product is named PlanLayer.
Read `docs/PRODUCT_SPEC.md` before changing application behavior.

Milestone 0 supplies packaging, SQLite initialization/health checks and tests.
Milestone 1 supplies persistent Fixed Event CRUD. Milestone 2 adds only persistent
Reminder CRUD and a mixed chronological display. A roadmap is
not authorization to implement it. Complete only the milestone requested.
Work for Milestone 2 belongs on `milestone-2-reminders`, with a Pull Request
against `main`. Do not commit to main or merge the PR automatically.
Do not introduce LLM/AI functionality, external calendar integrations,
authentication, background notification infrastructure, or other future scope
without an explicit request.

## Non-negotiable domain rules

- Fixed Events have a start and end datetime and occupy calendar time.
- Flexible Tasks have a deadline and positive estimated duration. An unscheduled
  task occupies no time. Scheduling creates an explicit linked time block;
  the deadline itself is never treated as a reservation.
- Reminders have a reminder datetime, occupy no time, and never cause conflicts.
  Exclude them from busy intervals, free-gap subtraction, and load calculations.
- Keep Reminder dataclasses, the reminders table and ReminderRepository separate
  from Events. A reminder has no start/end/duration fields. Do not turn it into
  a zero-duration event. Display composition must preserve its distinct type.
- Reminder range queries use `start <= reminder_datetime < end`. Multiple
  reminders at the same time and reminders inside events are valid.
- Milestone 2 adds no dismissal/completion state, notifications, recurrence,
  scheduling, load or gap calculations. Reminders are in-app information only.
- Use half-open intervals `[start, end)`. Adjacent intervals do not overlap.
- Events require `end > start`. Milestones 1–2 use local naive datetimes
  everywhere, including creation/update timestamps. Reject timezone-aware input.
  Do not add timezone conversion or UTC storage without a later request.
- Preserve the distinction between fixed-event conflicts and task-block
  collisions. Never silently move fixed events or overwrite task placements.
- Expand recurring events only within a bounded query window; include
  occurrences that start before the window but overlap it.
- Timezone and recurrence support are future work. The local-naive rule above
  supersedes the original specification's timezone proposal for this milestone.
- Recommendations and scheduling must be deterministic and explainable.
  Inject the current time into algorithms instead of reading the clock inside them.

## Stack and boundaries

Target Python 3.12+, Streamlit, SQLite, SQLAlchemy, pandas, Plotly,
python-dateutil, pytest, and ruff. Introduce dependencies only when a requested
implementation needs them; do not add frameworks speculatively.

Planned layers:

- `app.py`: Streamlit presentation entry point.
- `src/ui/`: Streamlit forms/cards; calls services, never database sessions.
- `src/services/`: application use cases, orchestration, transactions.
- `src/models/`: plain dataclasses. EventService and ReminderService validate
  their own input using small shared validators in `src/services/validation.py`.
- `src/engine/`: future pure scheduling
  algorithms; no Streamlit, SQLAlchemy, database access or network calls.
- `src/database/`: SQLAlchemy mappings, queries and session setup.

The requested foundation uses a literal `src` package. `src/utils/` remains
reserved for small helpers. ORM models and concrete repositories live under
`src/database/`; repository write operations own short-lived transactions.
UI calls services; services use domain algorithms and persistence.
Persistence must not import UI. Domain must not import services or persistence.
Keep ORM objects inside persistence/service boundaries; pass plain domain data
to algorithms and views. Keep pandas and Plotly in reporting/presentation;
do not make scheduling depend on DataFrames.

Do not put core business logic, SQL queries, recurrence expansion, conflict
detection or scheduling decisions inside Streamlit code. Streamlit reruns must
not repeat writes: mutate only through explicit user actions and service calls.

## Implementation style

- Write readable Python with type hints on function signatures.
- Prefer small functions, explicit names and straightforward data structures.
- Use dataclasses or similarly simple typed models where helpful.
- Avoid generic repository frameworks, dependency-injection containers,
  unnecessary inheritance, microservices and premature optimization.
- Explain non-obvious domain decisions, not obvious syntax.
- Validate in services/domain even when UI validation exists.
- Use explicit transaction boundaries and rollback on failed multi-step writes.
- Keep `initialize_database` and its health check working. `create_all` may add
  missing implemented tables; it must not drop data. Do not add Alembic yet.
- Do not commit secrets, local SQLite databases, caches or generated reports.
- Preserve unrelated user changes; inspect the working tree before editing.
- Keep documentation synchronized with intentional behavior changes.
  Ask for direction when a requested change would contradict a core invariant.

## Verification

For implemented algorithms, add pytest tests for normal cases and boundaries:
adjacency, overlap, containment, midnight, empty calendars, merged busy
intervals, recurrence limits, timezone/DST transitions, reminders excluded from
occupancy, task deadlines, insufficient capacity, and deterministic tie-breaking.
Test load/analytics to ensure overlapping blocks are not double-counted.

Use pure unit tests for domain algorithms and isolated temporary SQLite
databases for persistence/service integration tests. Never test against user data.
Do not require network access or a running Streamlit server for algorithm tests.

Once tooling exists, run the relevant tests, `ruff check .`, and
`ruff format --check .`; run the full suite when shared behavior changes.
Do not claim checks passed if they were not run. Documentation-only changes
require consistency and scope review, not application tests or new test tooling.

## Handoff

State what changed, which files were affected, the verification performed, and
any remaining limitations or design decisions. Keep the project simple enough
for a university student to explain the data model, algorithm tradeoffs and
layer boundaries in a technical interview.
