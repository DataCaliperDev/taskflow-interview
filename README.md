# TaskFlow

A task management REST API built with **FastAPI**, **SQLAlchemy**, and **SQLite**.

---

## 📌 PR overview — `candidate/myanh-truong`

This branch delivers **UC-1, UC-2, UC-4, UC-6, UC-9** as a single, scope-disciplined PR. Full reviewer-facing notes and the implementation plan live in `docs/`:

| Doc | What's in it |
|---|---|
| **[`docs/PR_NOTES.md`](docs/PR_NOTES.md)** | Per-UC breakdown, test plan, what's good / what's bad, in/out of scope, full reproduction recipe. **Start here.** |
| **[`docs/PLAN.md`](docs/PLAN.md)** | The implementation plan drafted before any code was changed; documents the decision tree (auth-migration strategy, scope discipline, harness rewrite) and reflects the final state. |

### 30-second summary

| UC | Change | State |
|---|---|---|
| **UC-1** | MD5 → `bcrypt` via `passlib`, with **verify-and-rehash on login** so legacy hashes upgrade silently. Pinned `bcrypt==4.2.1` (`passlib 1.7.4` breaks on bcrypt 5.x). | ✅ |
| **UC-2** | Removed `password_hash` from `UserOut` — one-line schema fix covers `/auth/register`, `/users/me`, `/users/`, `/users/{id}`. | ✅ |
| **UC-4** | `Settings(BaseSettings)` via `pydantic-settings`; required `SECRET_KEY` (no default); `.env.example` + `.gitignore`; app refuses to boot on missing secret. | ✅ |
| **UC-6** | `page` + `page_size` (max 100) on `GET /tasks/` and `GET /users/{id}/tasks`; DB-level offset/limit; `{items,total,page,page_size,total_pages}` envelope; `selectinload` + deterministic `order_by`; **frontend updated** with Prev/Next. | ✅ |
| **UC-9** | `EmailStr`, `Literal[…]` status, `Field(ge=1,le=3)` priority, min-length on `username`/`password`/`title`. | ✅ |

**Tests:** 22 passing. Test harness rewritten to in-memory SQLite with function-scoped fixtures (`tests/conftest.py`).

**Quick verification:**
```bash
cp .env.example .env
SECRET_KEY=test-secret-key .venv/bin/python -m pytest -v   # → 22 passed
```

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
