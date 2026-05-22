# UC-5 · Performance: N+1 Query

## 1) Problem Summary

`GET /tasks/summary/by-user` used an N+1 pattern:

- 1 query to load users
- 1 additional query per user to load tasks

As user count grew, database round-trips scaled linearly and degraded performance.

## 2) Solution, Trade-offs, and Assumptions

### Solution

- Rewrote summary loading with SQLAlchemy eager loading:
  - `joinedload(models.User.tasks)`
- Kept response shape unchanged:
  - `user_id`, `username`, `task_count`, `avg_priority_score`
- Added explanatory comment in endpoint describing:
  - original N+1 issue
  - why joinedload fixes it

### Trade-offs / Assumptions

- `joinedload` reduces query count to O(1) round-trips but may transfer more rows than pure SQL aggregation.
- Chosen to keep business scoring logic (`calculate_priority_score`) in one place (Python) instead of duplicating in SQL `CASE`.

## 3) How to Run Tests

Run UC-5 summary tests:

```bash
python -m pytest -q -k "summary_by_user"
```

Run full suite:

```bash
python -m pytest -q
```

