"""Pagination -- UC-6.

A *page* is a bounded slice of a larger collection. Every list
endpoint returns a page, never the full collection.

Wire shapes (``Page[T]``, ``PageDict``) live in ``app.schemas``;
this module owns the logic: how to read page selectors from the
request and how to slice a query at the database level.
"""

from __future__ import annotations

from math import ceil

from fastapi import Query
from sqlalchemy.orm import Query as SAQuery

from app.schemas import PageDict


class PageParams:
    """Page selection coming from the request: which page, how many
    per page. Out-of-range values are rejected at the boundary so the
    handler never sees a bad page number."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="1-indexed page number"),
        page_size: int = Query(
            10, ge=1, le=100, description="items per page (max 100)"
        ),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        """Records to skip before the current page begins."""
        return (self.page - 1) * self.page_size


def paginate(query: SAQuery, params: PageParams) -> PageDict:
    """Slice a collection into the requested page.

    The total and the page itself are read from the database (one
    counts, the other fetches the bounded slice) -- the application
    layer never loads the full collection into memory.
    """
    total = query.order_by(None).count()
    items = query.offset(params.offset).limit(params.page_size).all()
    total_pages = ceil(total / params.page_size) if params.page_size else 0
    return {
        "items": items,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "total_pages": total_pages,
    }
