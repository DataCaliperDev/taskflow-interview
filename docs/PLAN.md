# Implementation plan — UC-1, UC-2, UC-4, UC-6, UC-9

> **Workflow note.** This file is the implementation plan that drove the
> PR, drafted *before* any code was changed and kept here as a durable
> record of intent and trade-offs. Approach:
>
> 1. **Explore the codebase first** — read every relevant module, map existing patterns, confirm what was already in `requirements.txt` so the work reused libraries rather than adding them.
> 2. **Clarify the four highest-leverage decisions up front** (frontend update? auth-migration strategy? strict vs. pragmatic scope? touch the test harness?) — locked them in *before* writing the plan so the implementation phase had zero ambiguity.
> 3. **Write this plan** with file-by-file changes, edge cases, the test list, and a verification recipe.
> 4. **Execute** in the order recorded below (UC-4 → UC-2 → UC-1 → UC-9 → UC-6 → test harness → tests → end-to-end smoke).
> 5. **Update this file** after execution so it now records the *final* state, not the original forecast — including a couple of small additions noticed during testing.
>
> The reviewer-facing PR description lives in `docs/PR_NOTES.md`.

## Context

TaskFlow is an interview codebase deliberately seeded with bugs marked
`# Issue: ...`. The submission asks for five use cases, opened as a PR
from a `candidate/<name>` branch. None of the five were started before
this PR — only the comment annotations existed.

**Goal:** minimal, clean changes that satisfy each UC's "What we look
for" rubric, plus targeted tests. Other latent issues
(SQL injection in `/tasks/search`, missing ownership checks on
PUT/DELETE, magic-header admin in `DELETE /users/{id}`, N+1 in
`/tasks/summary/by-user`, etc.) are **noted in the PR description but
not fixed** — keeps the diff reviewable against the rubric.

## Final status

| UC | Ask | State |
|---|---|---|
| UC-1 | Replace MD5 with bcrypt (passlib) | ✅ Done with verify-and-rehash migration |
| UC-2 | Remove `password_hash` from API responses | ✅ Done at the schema layer |
| UC-4 | Move SECRET_KEY / DATABASE_URL to env via `pydantic-settings`; add `.env.example` | ✅ Done; app refuses to boot without `SECRET_KEY` |
| UC-9 | Pydantic validators for status / priority / EmailStr / min-length | ✅ Done with `Literal[…]` + `Field(ge=, le=, min_length=)` |
| UC-6 | `page`/`page_size`/metadata on `/tasks/` and `/users/{id}/tasks` | ✅ Done backend + frontend; deterministic order; N+1 avoided |

## Decisions (locked before implementation)

- **Frontend:** Updated `Tasks.jsx` consumption so the demo app keeps working after the response shape change.
- **Auth migration:** Verify-and-rehash on login — `verify_password` accepts both bcrypt and legacy MD5; on a successful MD5 login the row is transparently rehashed to bcrypt and committed.
- **Scope:** Strict — only the five UCs. Other known bugs documented in the PR description, not patched.
- **Test harness:** Replaced `conftest.py` with in-memory SQLite (`StaticPool`) + function-scoped fixtures; added an `authed_client` fixture.

## Implementation order (as executed)

UC-4 first (others read `settings.secret_key`), then UC-2 (one-line
schema change unblocks broader user-response work), then UC-1, UC-9,
UC-6. Tests added alongside each UC, not in a separate pass.

## File-by-file changes

### UC-4 · Config via pydantic-settings

- **`app/config.py`** — rewrote as `Settings(BaseSettings)` with `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`. Required (no default): `secret_key: str`. Optional with defaults: `database_url`, `algorithm`, `access_token_expire_minutes`, `app_name`, `app_version`, `debug`. Kept `DEFAULT_PAGE_SIZE`, `MAX_PAGE_SIZE`, `VALID_PRIORITIES`, `VALID_STATUSES` as plain module constants (not env-sourced). Exports `settings = Settings()`.
- **`app/database.py`** — reads `settings.database_url`.
- **`app/routers/auth.py`** — replaces `SECRET_KEY` / `ALGORITHM` / `ACCESS_TOKEN_EXPIRE_MINUTES` references with `settings.…`.
- **`app/main.py`** — reads `settings.app_name`, `settings.app_version`.
- **`.env.example`** (new) — documents `SECRET_KEY=` (required) plus `DATABASE_URL`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `DEBUG` with safe defaults.
- **`.gitignore`** (new) — `.env`, `*.db`, `__pycache__/`, `.venv/`, `.pytest_cache/`, `node_modules/`, `frontend/dist/`.
- **Tracked DB files** (`taskflow.db`, `test.db`) — removed from index via `git rm --cached`; working copies remain locally, gitignore prevents re-adding.

Missing-var failure mode: `Settings()` raises `pydantic.ValidationError` at import time if `SECRET_KEY` is unset and no `.env` is present.

### UC-1 · MD5 → bcrypt with graceful migration

- **`app/routers/auth.py`** — replaced both helpers with a `passlib` context. Shape:
  ```python
  pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

  def hash_password(password: str) -> str:
      return pwd_context.hash(password)

  def verify_password(plain: str, hashed: str) -> bool:
      if hashed.startswith("$2"):
          return pwd_context.verify(plain, hashed)
      # legacy raw-MD5 hex (constant-time compare)
      return hmac.compare_digest(hashed, hashlib.md5(plain.encode()).hexdigest())

  def needs_rehash(hashed: str) -> bool:
      return not hashed.startswith("$2")
  ```
  In `login()`, after a successful `verify_password`, if `needs_rehash(user.password_hash)` is true the row is rehashed to bcrypt and committed.
- **`requirements.txt`** — pinned `bcrypt==4.2.1` because `passlib 1.7.4` is incompatible with `bcrypt 5.x` (passlib can't introspect the version; bcrypt 5 raises strict `ValueError` for long inputs). Without the pin a fresh install hits two confusing runtime errors.
- No other call sites needed changes — `scripts/seed_data.py` and `app/routers/users.py` already go through `hash_password`.

### UC-2 · Strip `password_hash` from responses

- **`app/schemas.py`** — removed the `password_hash: str` line from `UserOut`. Single schema-level change covers `/auth/register`, `/users/`, `/users/me`, `/users/{id}` because they all share `UserOut` as `response_model`. No endpoint code touched.

### UC-9 · Input validation (Pydantic v2)

- **`app/schemas.py`** — tightened three schemas:
  - `UserCreate`: `email: EmailStr`, `username: str = Field(min_length=3, max_length=50)`, `password: str = Field(min_length=8)`.
  - `TaskCreate`: `title: str = Field(min_length=1, max_length=200)`, `status: Literal["todo","in_progress","done"] = "todo"`, `priority: int = Field(default=2, ge=1, le=3)`.
  - `TaskUpdate`: same constraints applied as `Optional[…]` via `Field(default=None, …)`.
  - `Literal` chosen over a custom validator — Pydantic v2 emits a clean error message, OpenAPI reflects the allowed values automatically.
- **`requirements.txt`** — added `email-validator==2.2.0` (Pydantic v2's `EmailStr` requires it as a separate install).

### UC-6 · Pagination

- **`app/schemas.py`** — added a concrete envelope:
  ```python
  class TaskPage(BaseModel):
      items: List[TaskOut]
      total: int
      page: int
      page_size: int
      total_pages: int
  ```
  Concrete over generic `Page[T]`: only two callers; concrete keeps the OpenAPI doc and the diff small.
- **`app/routers/tasks.py`** `list_tasks`:
  - `page: int = Query(1, ge=1)`, `page_size: int = Query(10, ge=1, le=100)`.
  - Query built at the DB level: `db.query(Task).options(selectinload(Task.comments))` plus optional `.filter(...)`.
  - `total = query.order_by(None).count()` — count without an order clause.
  - `items = query.order_by(Task.id).offset((page-1)*page_size).limit(page_size).all()` — deterministic ordering.
  - `total_pages = math.ceil(total / page_size) if total else 0`.
- **`app/routers/users.py`** `get_user_tasks` — same shape, query off `db.query(Task).filter(Task.owner_id == user_id)`. Returns `TaskPage`.
- **`selectinload(Task.comments)`** is necessary: without it, each row in the paginated page lazy-loads its comments during serialisation, reintroducing 1+N queries inside the handler.
- **Deterministic `order_by(Task.id)`** is necessary: without it, SQLite/Postgres may shuffle pages between requests and the same row can appear on multiple pages.
- **`frontend/src/api/client.js`** — `tasksApi.list()` signature unchanged; consumers now expect `{items, …}`.
- **`frontend/src/pages/Tasks.jsx`** — reads `.items` for the table, adds `page` state + Prev/Next footer that reads `total_pages` from the response. Stats row binds to `data.total` instead of `tasks.length`. Search path (`/tasks/search`) still returns a plain array; the page guards the render branch.

Edge cases handled by the formula: empty result → `total=0, total_pages=0, items=[]`; page beyond last → `items=[]` with valid `total`.

### Hygiene fix (noticed during testing)

- **`frontend/src/pages/Login.jsx`** — wrapped the hardcoded "Demo accounts: alice / alice123 (admin) · bob / bob123" banner in `{import.meta.env.DEV && (…)}`. Visible under `npm run dev`; Vite's dead-code elimination strips it entirely from production bundles (`npm run build && grep -c "Demo accounts" dist/assets/*.js` → `0`).

### Test harness rewrite

- **`tests/conftest.py`** — switched to `sqlite://` (in-memory) with `StaticPool` so the `TestClient` and any direct session share one connection. `Base.metadata.create_all` / `drop_all` per test. `scope="function"` for `db_session`, `client`, `test_user_token`. Added an `authed_client` fixture that wraps `TestClient` and injects the bearer header. Dropped the persistent `test.db` reference entirely. `os.environ.setdefault("SECRET_KEY", "test-secret-key")` at the top of the file so the runner works whether or not a developer has populated `.env`.

### Tests (lean — meaningful only)

Spread across the existing files; no new test modules.

- **`tests/test_auth.py`**
  - `test_register_response_omits_password_hash` (UC-2)
  - `test_stored_hash_is_bcrypt_not_plaintext` — register, query DB, assert hash ≠ password, hash ≠ MD5 of password, hash starts with `$2` (UC-1)
  - `test_legacy_md5_login_rehashes_to_bcrypt` — seed a user row with `hashlib.md5(...).hexdigest()` directly, log in successfully, refresh, assert hash starts with `$2` (UC-1)
  - Plus existing happy/sad path tests for register and login.

- **`tests/test_users.py`**
  - `test_me_response_omits_password_hash` (UC-2)
  - `test_list_users_response_omits_password_hash` (UC-2)
  - `test_register_rejects_invalid_email` (UC-9)
  - `test_register_rejects_short_password` (UC-9)
  - `test_register_rejects_short_username` (UC-9)
  - Plus unauthenticated-list assertion.

- **`tests/test_tasks.py`**
  - `test_create_task_rejects_invalid_status` (UC-9)
  - `test_create_task_rejects_priority_out_of_range` (UC-9)
  - `test_create_task_rejects_empty_title` (UC-9)
  - `test_update_task_rejects_invalid_status` (UC-9)
  - `test_list_tasks_returns_pagination_metadata` — assert key set, types, total matches inserted count (UC-6)
  - `test_list_tasks_respects_page_and_page_size` — insert 15, request page=2&page_size=10, assert `len(items)==5`, `page==2`, `total_pages==2`, page-1 and page-2 ids disjoint (UC-6)
  - `test_list_tasks_empty_returns_zero_metadata` — fresh DB; `{items:[], total:0, page:1, page_size:10, total_pages:0}` (UC-6)
  - `test_list_tasks_page_size_over_max_rejected` — page_size=101 → 422 (UC-6)
  - `test_user_tasks_paginated` — same envelope on `/users/{id}/tasks` (UC-6)
  - The order-dependent global `created_task_id` pattern is gone; tests use the `authed_client` fixture per case.

**Deliberately not added** (would have been noise):
- Multiple "valid input is accepted" tests per validator — every other test that creates a valid task or user covers that path implicitly.
- A dedicated `test_config.py` — `pydantic-settings` behaviour isn't ours to verify.
- Tests for endpoints not touched by this PR.

## Reused utilities / existing code

- `passlib.context.CryptContext` — already pulled in via `passlib[bcrypt]==1.7.4` in `requirements.txt:7`. No new dep needed for bcrypt itself, but the bcrypt subdep needs pinning (see UC-1 above).
- `pydantic_settings.BaseSettings` — `pydantic-settings==2.5.2` already in `requirements.txt:5`.
- `app/config.py:VALID_STATUSES` / `VALID_PRIORITIES` — kept as module constants for any caller that wants them, but UC-9 uses `Literal[...]` directly for cleaner Pydantic errors and OpenAPI exposure.
- `tests/conftest.py:override_get_db` — pattern kept; only the engine and scope changed.

## Verification (executed; results recorded)

```bash
# 1. Setup
git switch candidate/myanh-truong
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python scripts/seed_data.py    # → "Database seeded successfully."

# 2. Backend boots
.venv/bin/python run.py                  # → uvicorn LISTEN :8000

# 3. Login + legacy-MD5 rehash (alice was seeded with MD5)
TOKEN=$(curl -sX POST http://localhost:8000/auth/login \
  -d "username=alice&password=alice123" | jq -r .access_token)
.venv/bin/python -c "
from app.database import SessionLocal; from app.models import User
print(SessionLocal().query(User).filter_by(username='alice').one().password_hash[:7])"
#   → $2b$12$  (rehashed)

# 4. /users/me omits password_hash
curl -s http://localhost:8000/users/me -H "Authorization: Bearer $TOKEN" | jq
#   → no password_hash key

# 5. Pagination
curl -s "http://localhost:8000/tasks/?page=1&page_size=3" -H "Authorization: Bearer $TOKEN" | jq
#   → {items:[3 items], total:6, page:1, page_size:3, total_pages:2}
curl -i "http://localhost:8000/tasks/?page_size=999" -H "Authorization: Bearer $TOKEN"
#   → 422

# 6. Validation
curl -i -X POST http://localhost:8000/tasks/ -H "Authorization: Bearer $TOKEN" \
     -H 'Content-Type: application/json' -d '{"title":"x","priority":99}'
#   → 422
curl -i -X POST http://localhost:8000/auth/register -H 'Content-Type: application/json' \
     -d '{"username":"abc","email":"not-an-email","password":"longenough"}'
#   → 422

# 7. Tests
SECRET_KEY=test-secret-key .venv/bin/python -m pytest -v
#   → 22 passed

# 8. Frontend
cd frontend && npm install && npm run dev
#   → vite on :5173, proxies /auth /tasks /users to :8000
#   → log in as alice/alice123, tasks render via {items,...} envelope, Prev/Next works

# 9. Frontend production strips DEV-only credentials hint
npm run build && grep -c "Demo accounts" dist/assets/*.js
#   → 0

# 10. Missing-secret failure mode
mv .env .env.bak && unset SECRET_KEY
.venv/bin/python -c "from app.config import Settings; Settings()"
#   → pydantic.ValidationError: secret_key — Field required
mv .env.bak .env
```

## PR description outline (used as the basis for `docs/PR_NOTES.md`)

- **Summary:** Closes UC-1, UC-2, UC-4, UC-6, UC-9.
- **Per-UC bullets** with file pointers.
- **Trade-offs:** verify-and-rehash for backwards compatibility; concrete `TaskPage` instead of generic; tests intentionally lean; `bcrypt==4.2.1` pin to keep `passlib 1.7.4` working.
- **Out of scope (listed, not fixed):** SQL injection in `/tasks/search`, missing ownership checks on task/user mutations, magic-header admin in `DELETE /users/{id}`, N+1 in `/tasks/summary/by-user`, wide-open CORS, no rate limiting on `/auth/login`, `datetime.utcnow()` deprecation.
- **Running new tests:** `SECRET_KEY=test-secret-key pytest -v` (in-memory DB; no setup; 22 passing).
