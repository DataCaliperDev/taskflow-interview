# app/permissions.py

"""Authorization predicates (UC-3).

Ownership and admin privilege are two separate grounds for allowing a write:
you may act on what you own, and an admin may act on anything. Keeping the rule
in one place is what makes it consistent — four handlers previously had to spell
it out, and the one that forgot was the vulnerability.
"""

from fastapi import HTTPException, status

from app import models


def is_admin(user: models.User) -> bool:
    return user.role == "admin"


def require_owner_or_admin(
    current_user: models.User, owner_id: int, resource: str
) -> None:
    """Allow the owner of the resource, or any admin; raise 403 otherwise.

    Tasks pass task.owner_id and users pass their own id — "owner or admin" and
    "yourself or admin" are the same rule, only the field it reads differs.

    Call this after the row has been loaded: the owner is not known until then,
    which is also why it cannot be a FastAPI dependency. 404 therefore precedes
    403, so a caller can tell a missing resource from a forbidden one — at the
    cost of confirming that an id exists.
    """
    if current_user.id == owner_id or is_admin(current_user):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Not authorized to modify this {resource}",
    )
