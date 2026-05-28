# TaskFlow

Task management REST API. **FastAPI** + **SQLAlchemy 2.0** + **SQLite**.

This branch (`candidate/xuan-cuong`) addresses use cases **UC-3, UC-4, UC-5, UC-6, UC-12**.

---

## Quick start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure secrets
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into .env as SECRET_KEY

# 3. Seed sample data
python scripts/seed_data.py

# 4. Run
python run.py                                                  # http://localhost:8000
```

Interactive docs: `http://localhost:8000/docs`. OpenAPI: `/openapi.json`. Health: `/health`.

Seeded credentials:

| user  | password   | role   |
|-------|------------|--------|
| alice | alice123   | admin  |
| bob   | bob123     | member |
| carol | carol123   | member |

---

## Tests

```bash
pytest -q                            # full suite (38 tests)
pytest tests/test_tasks.py -q        # UC-3 / UC-5 / UC-6
pytest tests/test_users.py -q        # UC-3 / UC-6
pytest tests/test_auth.py  -q        # UC-12 hardening + duplicates
```

Tests use an in-memory SQLite DB and never touch `taskflow.db`.
`tests/conftest.py` injects a dummy `SECRET_KEY` for the test runner,
so `pytest` works without a populated `.env`.

---

## What changed

### UC-3 -- Authorization gaps

- `app/permissions.py` introduces `is_admin`, `require_admin`, `require_owner_or_admin`, `require_self_or_admin`.
- Task `PUT` / `DELETE`: **owner-or-admin** only.
- User `PUT`: **self-or-admin** only.
- User `DELETE`: **admin role** only; the `X-Admin-Override` magic header is gone.
- Regression test asserts the legacy header no longer bypasses the role check.

### UC-4 -- Configuration & secrets

- `app/config.py` is now a `pydantic-settings.BaseSettings` reading from environment / `.env`.
- `SECRET_KEY` has no default and requires `min_length=16`. The application refuses to start if it is missing (`ValidationError`).
- `.env.example` lists every key. `.env` and `*.db` are gitignored.

### UC-5 -- N+1 in `/tasks/summary/by-user`

- Original: 1 query for users + 1 query per user for their tasks.
- Fix: a single SQL aggregation -- `LEFT JOIN tasks` with `COUNT(tasks.id)` and `AVG(CASE ...)` matching the original priority-score formula.
- O(1) queries regardless of user count. Response schema unchanged.
- Rationale documented in the endpoint docstring.

### UC-6 -- Pagination

- `app/pagination.py` provides `PageParams` (FastAPI dependency, `page>=1`, `1<=page_size<=100`) and `paginate()` applying `OFFSET` / `LIMIT` at the SQLAlchemy query level.
- Wire shapes (`Page[T]` envelope, `PageDict` producer shape) live in `app.schemas`.
- Applied to `GET /tasks/` and `GET /users/{id}/tasks`.
- Response: `{items, total, page, page_size, total_pages}`.
- Tests cover empty results, mid page, last page, and the `page_size` cap (422).

### UC-12 -- Test suite

- `tests/conftest.py` rewritten:
  - in-memory SQLite (`sqlite://`) + `StaticPool` so the TestClient and direct sessions share one connection;
  - **function-scoped** fixtures, `drop_all` + `create_all` per test;
  - `get_db` dependency override (no module-scoped session leak);
  - seeded `alice` / `bob` / `carol` and `admin_token` / `bob_token` / `carol_token` fixtures;
  - `make_task` factory replaces the global `created_task_id`.
- Every test asserts on response body fields, not just status codes.
- 38 tests total, including authorization matrix on tasks and users, the `X-Admin-Override` regression, pagination edge cases, search, comments, duplicate registration, unauthenticated access, and `/tasks/summary/by-user` aggregation correctness.

### Performance hardening (carried in alongside UC-5/6)

- `selectinload(Task.comments)` on the catalog endpoints so paginated lists do not trigger one comment read per task during serialisation.
- Indexes on filter / lookup columns (`users.username`, `users.email`, `users.role`, `tasks.title`, `tasks.status`, `tasks.priority`, `tasks.owner_id`, `comments.task_id`, `comments.author_id`) plus a composite `(owner_id, status)` index for the common dashboard query.

### Repo-shape cleanups (carried in for clarity)

- `app/common/lookups.py::fetch_or_404` -- one helper replaces ten copies of "fetch by id or raise 404" across the routers.
- `JwtClaims` (TypedDict) and `Page[T]` / `PageDict` consolidated in `app/schemas.py` so wire shapes live in one module.
- Routers import `settings` from `app.config` directly; the legacy module-level constant shim is gone.

---

## Trade-offs / out of scope

| Item                                                        | Reason |
|-------------------------------------------------------------|--------|
| MD5 -> bcrypt password migration                            | Outside UC-3..6 scope; needs seed-data + DB migration. Flagged in `app/routers/auth.py::hash_password`. |
| `datetime.utcnow()` deprecation warnings                    | Pre-existing in `python-jose` and `auth.py`. Functional. |
| `@app.on_event("startup")` deprecation                      | Pre-existing FastAPI shape. |
| CORS `allow_origins=["*"]`                                  | Acceptable in dev; production hardening not in scope. |
| `app/utils/helpers.py` cleanup                              | Pre-existing latent issues; outside the assigned use cases. |

---

## Tech stack

| Layer        | Tool                              |
|--------------|-----------------------------------|
| Framework    | FastAPI 0.115                     |
| ORM          | SQLAlchemy 2.0                    |
| Validation   | Pydantic 2.9                      |
| Settings     | pydantic-settings 2.5             |
| Auth         | python-jose (JWT) + passlib       |
| DB (dev)     | SQLite                            |
| Tests        | pytest + httpx TestClient         |
