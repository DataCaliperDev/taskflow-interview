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
│   ├── permissions.py     # Ownership / role predicates
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
│   ├── test_authorization.py
│   ├── test_summary.py
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

Seeded accounts: `alice` / `alice123` (admin), `bob` / `bob123`,
`carol` / `carol123` (members).

---

## Running the tests

```bash
pytest tests/ -q                    # 93 passed, 3 xfailed
pytest tests/test_authorization.py -v
```

---

## What changed

**UC-1 · Password hashing**
- [x] MD5 replaced with bcrypt via `passlib`, one `CryptContext` in `auth.py`
- [x] Existing MD5 hashes still verify and are rewritten to bcrypt on first
      successful login, so no account needs a password reset
- [x] `bcrypt` pinned below 5.x — passlib 1.7.4 crashes on it, lazily, so the
      app boots and only auth requests fail
- [x] Unreadable hashes answer 401 rather than 500

**UC-2 · Password hash exposure**
- [x] `password_hash` masked at the schema layer, so all five routes returning
      a user are fixed at once
- [x] Marked deprecated in the OpenAPI schema, with removal one month out
- [x] Masking applied by a field serializer, which cannot be bypassed by
      passing an ORM object in directly

**UC-3 · Authorization**
- [x] `PUT`/`DELETE` on tasks and users restricted to the owner or an admin
- [x] `X-Admin-Override` removed from the handler signature entirely
- [x] Self-service account deletion preserved
- [x] One predicate in `app/permissions.py`, called from all four handlers

**UC-5 · N+1 query**
- [x] `GET /tasks/summary/by-user` is a single `LEFT JOIN` aggregation
- [x] One statement at any user count — was 1 + N, measured at 51 for 50 users
- [x] Response unchanged; `List[dict]` replaced by a declared `TaskSummaryRow`

**UC-12 · Test suite**
- [x] Function-scoped fixtures, database dropped and recreated per test
- [x] Global `created_task_id` replaced by a `make_task` factory
- [x] All fourteen original tests assert response bodies, not just status codes
- [x] 51 tests to 96, covering search, comments, tags, `/users/{id}/tasks`,
      unauthenticated access, invalid input and token edge cases

---

## Trade-offs and out of scope

| Decision | Reasoning |
|---|---|
| `password_hash` masked rather than deleted | No request logging exists to identify consumers, so removing the key outright would break an unknown client silently. One-month window, then deletion. |
| The scoring formula now lives in Python and in SQL | The cost of aggregating in the database instead of loading every task row. A parity test recomputes the result with `calculate_priority_score` and fails if the two drift. |
| `DELETE /users/{id}` is self-or-admin | The brief objects to how admin rights were established, not to self-deletion. Admin-only would silently remove it and break the frontend delete button. |
| 404 precedes 403 | The owner is unknown until the row is loaded. This confirms to a caller that an id exists; collapsing both into 404 would hide it but make authorised and unauthorised cases indistinguishable in tests. |
| Bcrypt makes the suite slower | About 30s, most of it hashing in fixtures. Lowering the cost factor for tests would exercise something other than the real configuration. |

**Not addressed** — each belongs to a use case not assigned here, and the three
marked with a test are listed above:

- SQL injection in `/tasks/search` (has an `xfail`)
- No validation on `priority`, `status`, email format or password strength
  (has an `xfail`)
- Duplicate usernames accepted at registration (has an `xfail`)
- `SECRET_KEY` hardcoded in `config.py`; no rate limiting on login
- `GET /tasks/{id}` and `GET /users/` readable by any authenticated caller —
  the brief covered update and delete, and `GET /tasks/` already lists every
  task to the frontend, so restricting reads is a product decision
- Deleting the last admin is possible and unrecoverable through the API, since
  no endpoint grants a role
- Deleting a user nulls `owner_id` on their tasks rather than removing them
- `POST` routes answer 200 where 201 would be correct
- `datetime.utcnow()` and `@app.on_event` deprecation warnings, both pre-existing

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
