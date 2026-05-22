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

Override the gate if needed:

```bash
python scripts/coverage_report.py --min-percent 80
```

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
