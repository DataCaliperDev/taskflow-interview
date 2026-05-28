# UC-9 · API Design: Input Validation

## 1) Problem Summary

Input validation in request schemas was too permissive:

- `status` accepted arbitrary strings
- `priority` accepted out-of-range integers
- `email` had no format validation
- minimum lengths were missing for `username`, `password`, and `title`

This allowed invalid payloads into API logic and persistence layers.

## 2) Solution, Trade-offs, and Assumptions

### Solution

- Updated `app/schemas.py` to use Pydantic v2 constraints:
  - `EmailStr` for email format validation
  - `Field(min_length=...)` for `username`, `password`, `title`
  - constrained task values:
    - status allowed set via literal type
    - priority range via `Field(ge=1, le=3)`
- Applied same constraints to `TaskUpdate` partial updates so update path cannot bypass create-time validation.
- Added tests for both valid and invalid inputs for each rule.

### Trade-offs / Assumptions

- Validation now fails earlier (422), which is expected and safer.
- Existing tests with too-short sample passwords were updated to valid values.

## 3) How to Run Tests

Run UC-9 focused tests:

```bash
python -m pytest -q -k "rejects_short or accepts_minimum or malformed_email or invalid_status or invalid_priority or empty_title"
```

Run full suite:

```bash
python -m pytest -q
```

Generate HTML coverage report:

```bash
python -m pytest --cov=app --cov-report=html
```

