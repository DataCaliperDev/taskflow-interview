# TaskFlow

A task management REST API built with **FastAPI**, **SQLAlchemy**, and **SQLite**.

---

## Branch `candidate/myanh-truong` — Implemented use cases

| UC | What changed | Status |
|---|---|---|
| **UC-1** | MD5 → `bcrypt` via `passlib` with verify-and-rehash on login — legacy hashes upgrade transparently. Pinned `bcrypt==4.2.1` for `passlib 1.7.4` compatibility. | ✅ |
| **UC-2** | Removed `password_hash` from `UserOut` schema — one-line fix covers all four user-returning endpoints. | ✅ |
| **UC-4** | `Settings(BaseSettings)` via `pydantic-settings`; `SECRET_KEY` required (app refuses to boot without it); `.env.example` added; `.env` gitignored. | ✅ |
| **UC-6** | `page` / `page_size` (max 100) on `GET /tasks/` and `GET /users/{id}/tasks`; DB-level offset/limit; `{items, total, page, page_size, total_pages}` envelope; `selectinload` + deterministic `order_by`; frontend Prev/Next. | ✅ |
| **UC-9** | `EmailStr`, `Literal["todo","in_progress","done"]` status, `Field(ge=1, le=3)` priority, `min_length` on `username` / `password` / `title`. | ✅ |

**Tests:** 22 passing. **Diff:** ~374 insertions / 207 deletions across 14 files. No incidental refactors.

### Running the tests

```bash
python3.13 -m venv .venv                         # 3.13 recommended (3.14 lacks pydantic-core wheel)
.venv/bin/pip install -r requirements.txt
SECRET_KEY=test-secret-key .venv/bin/python -m pytest -v   # → 22 passed
```

Tests use in-memory SQLite — no `.env`, no seed data required.

### Starting the full stack

```bash
# Backend
cp .env.example .env
.venv/bin/python scripts/seed_data.py   # seeds alice / bob / carol
.venv/bin/python run.py                 # → http://localhost:8000 · /docs

# Frontend (separate terminal)
cd frontend && npm install && npm run dev   # → http://localhost:5173
```

> Demo accounts only appear in the login UI during local dev (`import.meta.env.DEV`); stripped from production builds.

---

<details>
<summary><strong>📋 Per-UC breakdown</strong></summary>

### UC-1 · MD5 → bcrypt

**Problem.** `hash_password` used `hashlib.md5(password.encode()).hexdigest()`. MD5 is cryptographically broken; rainbow-table attacks recover plaintext in seconds.

**Solution.**
- Replaced both helpers with `passlib.context.CryptContext(schemes=["bcrypt"], deprecated="auto")`.
- `verify_password` accepts **both** bcrypt hashes (prefix `$2…`) and legacy raw-hex MD5. The MD5 branch uses `hmac.compare_digest` for constant-time comparison.
- After a successful MD5 login, `needs_rehash(...)` triggers a silent bcrypt rehash committed to the DB. No user-visible disruption.
- Pinned `bcrypt==4.2.1` — `passlib 1.7.4` is incompatible with `bcrypt 5.x` (`AttributeError: module 'bcrypt' has no attribute '__about__'` + `ValueError: password cannot be longer than 72 bytes`).

**Why verify-and-rehash, not a hard cutover.** A hard cutover would invalidate `alice123`, `bob123`, `carol123` the moment this merges. Verify-and-rehash keeps existing credentials working and migrates them on first login.

**Verify:**
```bash
curl -sX POST http://localhost:8000/auth/login -d "username=alice&password=alice123" | jq
.venv/bin/python -c "
from app.database import SessionLocal; from app.models import User
print(SessionLocal().query(User).filter_by(username='alice').one().password_hash[:7])"
# → $2b$12$
```

Test: `tests/test_auth.py::test_legacy_md5_login_rehashes_to_bcrypt`

---

### UC-2 · `password_hash` leak

**Problem.** `UserOut` exposed `password_hash: str`. Every user-returning endpoint leaked the hash.

**Solution.** Removed `password_hash` from `UserOut` in `app/schemas.py`. One-line schema change covers `/auth/register`, `/users/me`, `/users/`, `/users/{id}` automatically.

**Verify:**
```bash
TOKEN=$(curl -sX POST http://localhost:8000/auth/login -d "username=alice&password=alice123" | jq -r .access_token)
curl -s http://localhost:8000/users/me -H "Authorization: Bearer $TOKEN" | jq   # no password_hash key
```

Tests: `test_register_response_omits_password_hash`, `test_me_response_omits_password_hash`, `test_list_users_response_omits_password_hash`

---

### UC-4 · Config & secrets

**Problem.** `SECRET_KEY = "supersecretkey123"` hardcoded in source. Anyone with repo access could forge JWTs.

**Solution.**
- `app/config.py` rewritten as `Settings(BaseSettings)` with `SettingsConfigDict(env_file=".env", extra="ignore")`.
- `secret_key: str` — required, no default → unconfigured deployments raise `pydantic.ValidationError` at import time.
- `.env.example` documents every key. `.gitignore` covers `.env` and `*.db`.

**Verify graceful failure:**
```bash
mv .env .env.bak && unset SECRET_KEY
.venv/bin/python -c "from app.config import Settings; Settings()"
# → pydantic.ValidationError: secret_key — Field required
mv .env.bak .env
```

---

### UC-6 · Pagination

**Problem.** `GET /tasks/` returned the full table. Filtering happened in Python after a full `.all()`.

**Solution.**
- New `TaskPage` envelope: `{items, total, page, page_size, total_pages}`.
- `page: int = Query(1, ge=1)` and `page_size: int = Query(10, ge=1, le=100)`.
- Filtering and count pushed into SQLAlchemy: `query.order_by(None).count()` then `query.order_by(Task.id).offset(...).limit(...).all()`.
- `selectinload(Task.comments)` batches comment loading — without it, each row triggers a lazy-load during serialisation (N+1).
- Deterministic `order_by(Task.id)` — without it, the same row can appear on multiple pages.

**Edge cases:** empty result → `{total:0, total_pages:0}`; page beyond last → `{items:[], total:N}`; `page_size > 100` → 422.

**Verify:**
```bash
TOKEN=$(curl -sX POST http://localhost:8000/auth/login -d "username=alice&password=alice123" | jq -r .access_token)
curl -s "http://localhost:8000/tasks/?page=1&page_size=3" -H "Authorization: Bearer $TOKEN" | jq
curl -i "http://localhost:8000/tasks/?page_size=999" -H "Authorization: Bearer $TOKEN"  # → 422
```

Tests: `test_list_tasks_returns_pagination_metadata`, `test_list_tasks_respects_page_and_page_size`, `test_list_tasks_empty_returns_zero_metadata`, `test_list_tasks_page_size_over_max_rejected`, `test_user_tasks_paginated`

---

### UC-9 · Input validation

**Problem.** `TaskCreate` accepted any string for `status` and any int for `priority`. `UserCreate` accepted `"foo"` as a valid email. No min-length constraints.

**Solution (all in `app/schemas.py`):**
- `TaskCreate.status: Literal["todo", "in_progress", "done"] = "todo"` — chosen over a custom validator: better OpenAPI, cleaner error, zero custom code.
- `priority: int = Field(default=2, ge=1, le=3)`
- `title: str = Field(min_length=1, max_length=200)`
- `UserCreate.email: EmailStr` (added `email-validator==2.2.0` to requirements)
- `username: str = Field(min_length=3, max_length=50)`
- `password: str = Field(min_length=8)`

**Verify:**
```bash
curl -sX POST http://localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"username":"abc","email":"not-an-email","password":"longenough"}'   # → 422
TOKEN=$(curl -sX POST http://localhost:8000/auth/login -d "username=alice&password=alice123" | jq -r .access_token)
curl -sX POST http://localhost:8000/tasks/ -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"title":"x","priority":99}'    # → 422
```

Tests: one per rule — `test_create_task_rejects_invalid_status`, `test_create_task_rejects_priority_out_of_range`, `test_create_task_rejects_empty_title`, `test_update_task_rejects_invalid_status`, `test_register_rejects_invalid_email`, `test_register_rejects_short_password`, `test_register_rejects_short_username`

</details>

---

<details>
<summary><strong>🧪 Test plan & harness</strong></summary>

### Test coverage

| File | UCs | What it covers |
|---|---|---|
| `tests/test_auth.py` | UC-1, UC-2 | register/login happy paths, hash-not-plaintext, hash starts with `$2`, legacy-MD5 rehash on login, register response omits hash |
| `tests/test_users.py` | UC-2, UC-9 | `/users/me` and `/users/` omit hash; unauthenticated 401; bad email / short password / short username rejected |
| `tests/test_tasks.py` | UC-6, UC-9 | bad status / out-of-range priority / empty title / bad update status rejected; pagination metadata shape; page/page_size; empty result; over-max; `/users/{id}/tasks` paginated |

### Why the harness was rewritten

The original `tests/conftest.py` had three problems:
1. `scope="module"` — tests in the same file shared one DB; a mutation in test A silently affected test B.
2. Persistent `test.db` — `pytest` twice on a fresh checkout could give different results.
3. No teardown — `test.db` left on disk.

Rewritten: in-memory SQLite (`sqlite://` + `StaticPool`), `scope="function"` on all fixtures, `create_all`/`drop_all` per test, `authed_client` fixture injects the bearer header automatically.

</details>

---

<details>
<summary><strong>✅ What's good &nbsp;/&nbsp; ⚠️ What's bad</strong></summary>

### What's good

- **Strict scope** — every line maps to a UC. Zero incidental refactors.
- **One-line UC-2 fix** — schema-level removal covers all four endpoints; future `UserOut` callers are safe by default.
- **Verify-and-rehash** — existing credentials keep working and migrate silently.
- **DB-level pagination** — filters and count both push into SQLAlchemy; handler never loads the full table.
- **N+1 avoided** — `selectinload(Task.comments)` on both paginated list endpoints.
- **Deterministic pagination** — explicit `order_by(Task.id)` prevents cross-request page drift.
- **Schema-level constraints** — UC-9 validates at the request boundary; handlers never see invalid data.
- **`Literal` over custom validators** — cleaner OpenAPI, better error messages, less code.
- **Dependency pin catch** — `bcrypt==4.2.1` prevents a silent regression from `passlib 1.7.4` + `bcrypt 5.x` incompatibility.
- **Test harness rebuilt first** — function-scoped, in-memory; tests run reliably in any order.
- **Fail-fast on misconfiguration** — `SECRET_KEY` has no default; app crashes at import with a clear error.

### What's bad / known weaknesses

- **Two exact-version pins** — `email-validator==2.2.0` and `bcrypt==4.2.1`. Pragmatic here but a long-lived project would use `~=` compatible-release pins.
- **`UserOut` is both public and internal** — removing `password_hash` means any app code that legitimately needs the hash must read it off the ORM object directly, not via the schema. A `UserPublic`/`UserInternal` split would be cleaner but was out of scope.
- **`/tasks/search` still returns a raw list** — not in UC-6's scope; the frontend handles both shapes, but a consistent API would paginate it too.
- **`datetime.utcnow()` deprecation warnings** in `app/routers/auth.py` — pre-existing, 64 warnings in `pytest` output. Functional today.
- **`@app.on_event("startup")` deprecation** in `app/main.py` — pre-existing; should migrate to `lifespan`.

### Given more time (within UC spirit)

- Split `UserOut` → `UserPublic` + `UserInternal`. ~10 lines.
- `SECRET_KEY: str = Field(..., min_length=16)` to reject low-entropy keys at boot.
- Return explicit 400 on duplicate username registration (currently 500 `IntegrityError`).
- `raise credentials_exception from None` in `get_current_user` to suppress JWT exception chaining.

</details>

---

<details>
<summary><strong>🎯 In scope &nbsp;/&nbsp; Out of scope</strong></summary>

### In scope

| File | UC(s) |
|---|---|
| `app/config.py` | UC-4 |
| `app/database.py` | UC-4 |
| `app/main.py` | UC-4 |
| `app/routers/auth.py` | UC-1, UC-4 |
| `app/routers/tasks.py` | UC-6 |
| `app/routers/users.py` | UC-6 |
| `app/schemas.py` | UC-2, UC-6, UC-9 |
| `requirements.txt` | UC-1, UC-9 |
| `frontend/src/pages/Tasks.jsx` | UC-6 |
| `frontend/src/pages/Login.jsx` | hygiene (noticed during testing) |
| `tests/conftest.py` | prerequisite for new tests |
| `tests/test_auth.py` | UC-1, UC-2 |
| `tests/test_users.py` | UC-2, UC-9 |
| `tests/test_tasks.py` | UC-6, UC-9 |
| `.env.example`, `.gitignore` | UC-4 |

### Out of scope (noticed, not fixed)

| Defect | Where | Note |
|---|---|---|
| **SQL injection** in `/tasks/search` | `app/routers/tasks.py` | Raw `f"SELECT * FROM tasks WHERE title LIKE '%{q}%'"` — one-line ORM fix but separate UC |
| **Missing ownership checks** on task/user mutations | `tasks.py`, `users.py` | Any authenticated user can mutate any task or profile |
| **Magic-header admin** in `DELETE /users/{id}` | `users.py` | `x_admin_override: str = Header("admin-secret-2024")` |
| **N+1 in `/tasks/summary/by-user`** | `tasks.py` | Needs a `GROUP BY` aggregation |
| **CORS `allow_origins=["*"]` + `allow_credentials=True`** | `main.py` | Browsers reject this combo; production hardening needed |
| **No rate limiting on `/auth/login`** | `auth.py` | Brute-force exposure |

</details>

---

<details>
<summary><strong>⚖️ Trade-offs &amp; decisions</strong></summary>

| Decision | Alternative | Why |
|---|---|---|
| **Verify-and-rehash** for MD5→bcrypt | Hard cutover (re-seed) | Keeps existing credentials valid; zero operator action; gradual migration |
| **Concrete `TaskPage` schema** | Generic `Page[T]` | Only two callers; concrete reads more clearly in OpenAPI |
| **`Literal[...]` for status** | Custom `@field_validator` | Better OpenAPI; better error message; zero custom code |
| **Frontend updated** | Backend-only | UC-6 doesn't explicitly say to update the frontend, but a broken demo is worse |
| **In-memory SQLite for tests** | File-based fresh-per-test | Faster; no artefacts; no concurrency surprises with `StaticPool` |
| **Function-scoped fixtures** | Module-scoped | Tests run in any order; no shared state |
| **22 tests** | Larger coverage matrix | Brief said "don't write too many unnecessary obvious tests" |
| **Pinned `bcrypt==4.2.1`** | Floating | `passlib 1.7.4` breaks on `bcrypt 5.x` |
| **Did not split `UserOut`** | `UserPublic` + `UserInternal` | UC-2 only needs the leak fixed; one line is enough |
| **Did not change register to 201** | Fix HTTP semantics | Existing tests assert `200`; changing it is out of UC scope |

</details>

---

<details>
<summary><strong>🔬 Full reproduction recipe</strong></summary>

```bash
# 0. Branch
git switch candidate/myanh-truong

# 1. Python deps
python3.13 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 2. Configure secret
cp .env.example .env

# 3. Tests (22 passing, no seed needed)
SECRET_KEY=test-secret-key .venv/bin/python -m pytest -v

# 4. Seed + backend
rm -f taskflow.db
.venv/bin/python scripts/seed_data.py
.venv/bin/python run.py &

# 5. Frontend
cd frontend && npm install && npm run dev &

# 6. UC-1 + UC-2: login, verify rehash, verify no password_hash
TOKEN=$(curl -sX POST http://localhost:5173/auth/login \
  -d "username=alice&password=alice123" | jq -r .access_token)
curl -s http://localhost:5173/users/me -H "Authorization: Bearer $TOKEN" | jq
# → no password_hash key; alice's DB row now has $2b$12$ hash

# 7. UC-6: pagination
curl -s "http://localhost:5173/tasks/?page=1&page_size=3" -H "Authorization: Bearer $TOKEN" | jq
# → {items:[3 tasks], total:6, page:1, page_size:3, total_pages:2}
curl -i "http://localhost:5173/tasks/?page_size=999" -H "Authorization: Bearer $TOKEN"
# → 422

# 8. UC-9: validation rejection
curl -iX POST http://localhost:5173/tasks/ \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"x","priority":99}'
# → 422

# 9. UC-4: fail-fast on missing secret
mv .env .env.bak && unset SECRET_KEY
.venv/bin/python -c "from app.config import Settings; Settings()"
# → pydantic.ValidationError: secret_key — Field required
mv .env.bak .env

# 10. Production build strips the demo-credentials hint
cd frontend && npm run build && grep -c "Demo accounts" dist/assets/*.js
# → 0
```

</details>

---

<details>
<summary><strong>🧠 Implementation plan</strong></summary>

> Drafted before any code was changed. Documents the decision tree, implementation order, and file-by-file changes. Updated to reflect the final state.

### Decisions locked before implementation

- **Frontend:** updated `Tasks.jsx` so the demo app keeps working after the response shape change.
- **Auth migration:** verify-and-rehash — `verify_password` accepts both bcrypt and legacy MD5; successful MD5 login transparently rehashes the row.
- **Scope:** strict — only the five UCs. Other known bugs documented but not patched.
- **Test harness:** replaced `conftest.py` with in-memory SQLite (`StaticPool`) + function-scoped fixtures.

### Implementation order (as executed)

UC-4 first (others read `settings.secret_key`) → UC-2 (schema unblocks user-response work) → UC-1 → UC-9 → UC-6 → test harness → tests → end-to-end smoke.

### File-by-file changes

**UC-4 · `app/config.py`** — `Settings(BaseSettings)` with `SettingsConfigDict(env_file=".env", extra="ignore")`. Required: `secret_key`. Optional with defaults: `database_url`, `algorithm`, `access_token_expire_minutes`, `app_name`, `app_version`, `debug`. Exports `settings = Settings()`. Module constants `DEFAULT_PAGE_SIZE`, `MAX_PAGE_SIZE`, `VALID_PRIORITIES`, `VALID_STATUSES` kept as plain constants.

**UC-4 · `app/database.py`** — reads `settings.database_url`.

**UC-4 · `app/routers/auth.py`** — replaces hardcoded `SECRET_KEY` / `ALGORITHM` / `ACCESS_TOKEN_EXPIRE_MINUTES` with `settings.…`.

**UC-4 · `app/main.py`** — reads `settings.app_name`, `settings.app_version`.

**UC-4 · `.env.example`** (new) — documents `SECRET_KEY` (required) and optional vars with safe defaults.

**UC-4 · `.gitignore`** (new) — `.env`, `*.db`, `__pycache__/`, `.venv/`, `.pytest_cache/`, `node_modules/`, `frontend/dist/`.

**UC-1 · `app/routers/auth.py`** — replaced helpers with `passlib.context.CryptContext`. Shape:

```python
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    if hashed.startswith("$2"):
        return pwd_context.verify(plain, hashed)
    return hmac.compare_digest(hashed, hashlib.md5(plain.encode()).hexdigest())

def needs_rehash(hashed: str) -> bool:
    return not hashed.startswith("$2")
```

After a successful login, `needs_rehash(user.password_hash)` triggers an inline rehash committed to the DB.

**UC-1 · `requirements.txt`** — pinned `bcrypt==4.2.1`.

**UC-2 · `app/schemas.py`** — removed `password_hash: str` from `UserOut`. One line.

**UC-9 · `app/schemas.py`** — `UserCreate`: `email: EmailStr`, `username: str = Field(min_length=3, max_length=50)`, `password: str = Field(min_length=8)`. `TaskCreate`: `title: str = Field(min_length=1, max_length=200)`, `status: Literal["todo","in_progress","done"] = "todo"`, `priority: int = Field(default=2, ge=1, le=3)`. `TaskUpdate`: same as `Optional[…]`.

**UC-9 · `requirements.txt`** — added `email-validator==2.2.0`.

**UC-6 · `app/schemas.py`** — added `TaskPage(BaseModel)` with `items`, `total`, `page`, `page_size`, `total_pages`.

**UC-6 · `app/routers/tasks.py`** — `list_tasks` returns `TaskPage`, accepts `page`/`page_size` query params, filters and paginates at DB level with `selectinload(Task.comments)` and deterministic `order_by(Task.id)`.

**UC-6 · `app/routers/users.py`** — `get_user_tasks` same shape.

**UC-6 · `frontend/src/pages/Tasks.jsx`** — reads `.items` from the envelope, adds `page` state, Prev/Next footer, resets page on filter/search change.

**Hygiene · `frontend/src/pages/Login.jsx`** — wrapped demo-credentials banner in `{import.meta.env.DEV && (…)}`.

**Test harness · `tests/conftest.py`** — in-memory SQLite + `StaticPool`, `scope="function"` on all fixtures, `authed_client` fixture, `os.environ.setdefault("SECRET_KEY", "test-secret-key")` at top.

</details>

---

## Project Structure

```
taskflow/
├── app/
│   ├── config.py          # App configuration (UC-4)
│   ├── database.py        # SQLAlchemy engine & session
│   ├── main.py            # FastAPI app & router registration
│   ├── models.py          # ORM models (User, Task, Comment)
│   ├── schemas.py         # Pydantic request/response schemas (UC-2, UC-6, UC-9)
│   ├── routers/
│   │   ├── auth.py        # Registration, login, JWT (UC-1, UC-4)
│   │   ├── tasks.py       # Task CRUD + comments (UC-6)
│   │   └── users.py       # User management (UC-6)
│   └── utils/
│       └── helpers.py     # Shared utility functions
├── tests/
│   ├── conftest.py        # Pytest fixtures (rewritten: in-memory, function-scoped)
│   ├── test_auth.py       # UC-1, UC-2
│   ├── test_tasks.py      # UC-6, UC-9
│   └── test_users.py      # UC-2, UC-9
├── scripts/
│   └── seed_data.py       # Seed DB with sample data
├── .env.example           # Required and optional env vars (UC-4)
├── requirements.txt
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
| Web framework | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (dev) |
| Auth | python-jose (JWT) + passlib (bcrypt) |
| Validation | Pydantic v2 + pydantic-settings |
| Testing | pytest + httpx TestClient |
