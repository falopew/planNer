# PlanLayer development rules

## Project and scope

PlanLayer is a smart personal calendar and life-planning portfolio project.
The GitHub repository is named `planNer`; the product is named PlanLayer.
Read `docs/PRODUCT_SPEC.md` before changing application behavior.

The current milestone is documentation and specification only. Do not create
application code, dependency configuration, database files, or UI scaffolding
until implementation is explicitly requested. A roadmap is not authorization
to implement it. Complete only the milestone or change requested by the user.
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
- Use half-open intervals `[start, end)`. Adjacent intervals do not overlap.
- Require `end > start` and timezone-aware datetimes at domain boundaries.
- Preserve the distinction between fixed-event conflicts and task-block
  collisions. Never silently move fixed events or overwrite task placements.
- Expand recurring events only within a bounded query window; include
  occurrences that start before the window but overlap it.
- Use the user's IANA timezone for local dates and recurrence. Use UTC instants
  for stored one-off timestamps and comparisons.
- Recommendations and scheduling must be deterministic and explainable.
  Inject the current time into algorithms instead of reading the clock inside them.

## Stack and boundaries

Target Python 3.12+, Streamlit, SQLite, SQLAlchemy, pandas, Plotly,
python-dateutil, pytest, and ruff. Introduce dependencies only when a requested
implementation needs them; do not add frameworks speculatively.

Planned layers:

- `src/planlayer/ui/`: Streamlit views, forms, presentation and session state.
- `src/planlayer/services/`: application use cases, orchestration, transactions.
- `src/planlayer/domain/`: plain typed models, validation and pure scheduling
  algorithms; no Streamlit, SQLAlchemy, database access or network calls.
- `src/planlayer/persistence/`: SQLAlchemy mappings, queries and session setup.

These are planned paths, not a requirement to scaffold them now.
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
