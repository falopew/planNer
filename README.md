# PlanLayer

A personal calendar and life-planning portfolio project. Future milestones
will distinguish Fixed Events, Flexible Tasks and Reminders and add calendar
views and explainable scheduling. No LLM/AI functionality is included.

## Current status

Milestone 0 — Project Foundation: Python packaging, a minimal Streamlit screen,
SQLite initialization and connection health check, and database tests.
Events, tasks, reminders, calendars, scheduling and recommendations are **not
implemented**. The database has no application tables yet.

## Architecture

```text
app.py                  Streamlit presentation entry point
src/__init__.py         Application package
src/database/db.py      SQLAlchemy engine, SQLite initialization and health check
src/models/             Reserved for future models
src/services/           Reserved for application orchestration
src/engine/             Reserved for pure domain/scheduling algorithms
src/utils/              Reserved for small shared helpers
tests/test_database.py  Isolated SQLite tests
tests/test_app.py       Streamlit success, rerun and failure smoke tests
data/                   Local database (ignored by Git)
assets/                 Reserved for visual assets
```

The UI delegates database initialization and queries to `src/database`.
Future UI actions will call services, which coordinate persistence and pure
engine functions. Core business logic must remain outside Streamlit.

The literal `src` package follows the requested foundation layout; it is not
the conventional `src/planlayer` packaging layout. Models and algorithms will
be added only in their requested milestones.

## Installation (Python 3.12+)

From PowerShell on Windows:

```powershell
git clone https://github.com/falopew/planNer.git
cd planNer
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

Open http://localhost:8501. The screen shows the title, description and
database connection status. Stop the server with Ctrl+C.

Startup creates `data/planlayer.db` if missing; the default path is anchored
to the repository, independent of the terminal working directory. Existing
data is preserved. SQLite foreign keys are enabled on every connection.
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
```

On macOS/Linux replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.
Tests use temporary databases and never touch `data/planlayer.db`.

Read [AGENTS.md](AGENTS.md) for development rules and
[the product specification](docs/PRODUCT_SPEC.md) for the planned roadmap.
