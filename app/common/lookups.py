"""Generic "fetch a record or raise 404" helper.

Every endpoint that resolves a record by id needs the same three
lines: query, ``first()``, raise 404 if missing. Extracted here so
the rule lives in one place and routers stop repeating themselves.
"""

from __future__ import annotations

from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import Base

T = TypeVar("T", bound=Base)


def fetch_or_404(db: Session, model: type[T], record_id: int, label: str) -> T:
    """Return the record with ``record_id``; raise 404 if it is missing.

    ``label`` is the noun the caller wants in the error message
    (e.g. ``"Task"``, ``"User"``) so the response stays in domain
    language instead of leaking model class names.
    """
    record = db.query(model).filter(model.id == record_id).first()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{label} not found",
        )
    return record
