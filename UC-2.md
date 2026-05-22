# UC-2 · Security: Sensitive Data Exposure

## 1) Problem Summary

User-facing responses were exposing `password_hash` through the user response schema.  
Because multiple endpoints shared the same response model, the leak appeared in:

- `POST /auth/register`
- `GET /users/me`
- `GET /users/`
- `GET /users/{id}`
- `PUT /users/{id}`

This is sensitive-data exposure: password hashes should never be returned by API responses.

## 2) Solution, Trade-offs, and Assumptions

### Solution

- Removed `password_hash` from `UserOut` in `app/schemas.py`.
- Kept `password_hash` in the DB model (`app/models.py`) for internal auth logic only.
- Added/updated tests to assert `password_hash` is absent in user-facing responses.

### Why schema-level

A schema-level fix is safer than endpoint-by-endpoint filtering:

- one source of truth
- future endpoints reusing `UserOut` inherit the safe behavior automatically

### Trade-offs / Assumptions

- This UC targets output exposure, not password-hashing algorithm quality.
- Existing auth flow still depends on stored hash internally, which remains unchanged.

## 3) How to Run Tests

Run only UC-2 related tests:

```bash
python -m pytest -q -k "register or get_me or list_users_authenticated"
```

Run full suite:

```bash
python -m pytest -q
```

