# UC-3 · Security: Authorization Gaps

## 1) Problem Summary

Authorization rules were inconsistent:

- Any authenticated user could update/delete tasks they did not own.
- User deletion used a magic header (`X-Admin-Override`) instead of role-based checks.

This allowed privilege abuse and bypass-like behavior.

## 2) Solution, Trade-offs, and Assumptions

### Solution

- Added centralized authorization helpers in `app/routers/auth.py`:
  - `is_admin(...)`
  - `require_owner_or_admin(...)`
  - `require_admin(...)`
- Enforced owner-or-admin checks in:
  - `PUT /tasks/{task_id}`
  - `DELETE /tasks/{task_id}`
  - `DELETE /users/{user_id}`
- Removed reliance on magic header for admin behavior.
- Added tests for owner / non-owner / admin paths and a regression test proving the old header no longer grants access.

### Trade-offs / Assumptions

- Kept self-delete behavior for users.
- Scope focused on required endpoints; did not broaden policy to unrelated routes.

## 3) How to Run Tests

Run UC-3 focused tests:

```bash
python -m pytest -q -k "owner or non_owner or admin_can or magic_header or delete_self"
```

Run full suite:

```bash
python -m pytest -q
```

