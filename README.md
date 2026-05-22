# TaskFlow

A task management REST API built with **FastAPI**, **SQLAlchemy**, and **SQLite**.

---

## Branch `candidate/myanh-truong` — Implemented use cases

| UC | What changed | Status |
|---|---|---|
| **UC-1** | MD5 → `bcrypt` via `passlib` with verify-and-rehash on login — legacy hashes upgrade transparently without breaking seed accounts. Pinned `bcrypt==4.2.1` for `passlib 1.7.4` compatibility. | ✅ |
| **UC-2** | Removed `password_hash` from `UserOut` schema — covers every endpoint (`/auth/register`, `/users/me`, `/users/`, `/users/{id}`). | ✅ |
| **UC-4** | `Settings(BaseSettings)` via `pydantic-settings`; `SECRET_KEY` required (no default — app refuses to boot without it); `.env.example` added; `.env` gitignored. | ✅ |
| **UC-6** | `page` / `page_size` (max 100) on `GET /tasks/` and `GET /users/{id}/tasks`; DB-level `offset`/`limit`; `{items, total, page, page_size, total_pages}` response envelope; `selectinload` + deterministic `order_by`; frontend Prev/Next navigation. | ✅ |
| **UC-9** | `EmailStr`, `Literal["todo","in_progress","done"]` status, `Field(ge=1, le=3)` priority, `min_length` on `username` / `password` / `title` — all validated at the schema boundary. | ✅ |

### Running the tests

```bash
# One-time setup
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Run (in-memory SQLite, no .env needed)
SECRET_KEY=test-secret-key .venv/bin/python -m pytest -v
# → 22 passed
```

### Starting the full stack

```bash
# Backend
cp .env.example .env          # fill in SECRET_KEY
python scripts/seed_data.py   # seed alice / bob / carol
python run.py                 # http://localhost:8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

> Demo accounts only appear in the login UI during local dev (`import.meta.env.DEV`); they are stripped from production builds.

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
