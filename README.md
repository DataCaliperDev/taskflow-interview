# TaskFlow

A task management REST API built with **FastAPI**, **SQLAlchemy**, and **SQLite**.
---

## Project Structure

```
taskflow/
├── app/
│   ├── config.py          # App configuration
│   ├── database.py        # SQLAlchemy engine & session
│   ├── main.py            # FastAPI app & router registration
│   ├── models.py          # ORM models (User, Task, Comment)
│   ├── schemas.py         # Pydantic request/response schemas
│   ├── routers/
│   │   ├── auth.py        # Registration, login, JWT
│   │   ├── tasks.py       # Task CRUD + comments
│   │   └── users.py       # User management
│   └── utils/
│       └── helpers.py     # Shared utility functions
├── tests/
│   ├── conftest.py        # Pytest fixtures
│   ├── test_auth.py
│   ├── test_tasks.py
│   └── test_users.py
├── scripts/
│   └── seed_data.py       # Seed DB with sample data
├── TASKS.md               # Candidate use cases
├── EVALUATOR_GUIDE.md     # Interviewer reference (do not share with candidates)
├── requirements.txt
├── .env.example
└── run.py
```

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Seed the database
python scripts/seed_data.py

# 3. Start the server
python run.py
```

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- OpenAPI schema: http://localhost:8000/openapi.json

## Docker Implementation and Running Guide

### Docker files in this project

- `Dockerfile` - backend image (FastAPI + Uvicorn)
- `frontend/Dockerfile` - frontend image (React + Vite dev server)
- `docker-compose.yml` - multi-container setup for backend + frontend
- `.dockerignore` and `frontend/.dockerignore` - smaller/faster Docker builds

### Prerequisites

- Docker Desktop installed and running
- A local `.env` file in the project root (used by the backend service)

If needed, create `.env` from the example:

```bash
cp .env.example .env
```

### Run with Docker Compose

From the repository root:

```bash
docker compose up --build
```

This starts:

- `backend` on port `8000`
- `frontend` on port `5173`

### Access URLs

- Frontend: http://localhost:5173
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Useful commands

Start in background:

```bash
docker compose up --build -d
```

View logs:

```bash
docker compose logs -f
```

Stop containers:

```bash
docker compose down
```

Stop and remove database volume (clean reset):

```bash
docker compose down -v
```

## Test Coverage

Run tests and print app-code coverage percentage:

```bash
python scripts/coverage_report.py
```

The command fails when coverage is below 80% (default gate).

Print only the numeric percentage (useful for scripts/CI):

```bash
python scripts/coverage_report.py --percent-only
```

Generate the full HTML coverage report:

```bash
python -m pytest --cov=app --cov-report=html
```

Then open:

```text
htmlcov/index.html
```

Override the gate if needed:

```bash
python scripts/coverage_report.py --min-percent 80
```

## UC Documents

Detailed implementation notes are available per use case:

- `UC-2.md` — Sensitive Data Exposure
- `UC-3.md` — Authorization Gaps
- `UC-5.md` — N+1 Query Performance
- `UC-9.md` — Input Validation
- `UC-12.md` — Test Suite Improvement

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Web framework | FastAPI 0.110 |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (dev) |
| Auth | python-jose (JWT) + passlib |
| Validation | Pydantic v2 |
| Testing | pytest + httpx TestClient |
