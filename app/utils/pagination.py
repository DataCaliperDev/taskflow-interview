# pagination.py
from fastapi import Query
from pydantic import BaseModel
from typing import Generic, TypeVar, List
from math import ceil

from sqlalchemy import select, func
from sqlalchemy.orm import Session

class PaginationParams(BaseModel):
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def pagination_params(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size)


T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int


def paginate_query(db: Session, base_query, pagination):
    total = db.execute(
        select(func.count()).select_from(base_query.subquery())
    ).scalar_one()

    items = db.execute(
        base_query.offset(pagination.offset).limit(pagination.limit)
    ).scalars().all()

    total_pages = ceil(total / pagination.page_size) if total else 0

    return items, total, total_pages
