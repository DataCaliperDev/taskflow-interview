"""Authorization rules -- UC-3.

Two domain concepts decide who may act on a record:

    Ownership   -- a user *owns* a task they created, and *owns* their
                   own profile.
    Admin role  -- a user with ``role == "admin"`` may act on any task
                   or any profile, regardless of ownership.

Members may act on records they own. Admins may act on any record.
Nothing else grants access -- the legacy ``X-Admin-Override`` header
is gone.

All three predicates raise 403 with a domain-shaped reason; routers
call them as the first action inside the handler so the reader can
see the rule at the top of every protected endpoint.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from app import models

_ADMIN_ROLE = "admin"


def is_admin(user: models.User) -> bool:
    """A user is an admin iff their stored role equals ``"admin"``."""
    # ``bool(...)`` keeps the value a plain Python bool even when the
    # comparison comes from an ORM column.
    return bool(user.role == _ADMIN_ROLE)


def require_admin(user: models.User) -> None:
    """Allow admins through; reject everyone else.

    Used for actions that no member should ever perform on their own
    behalf, such as deleting another user.
    """
    if not is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )


def require_owner_or_admin(user: models.User, resource_owner_id: int) -> None:
    """Allow the owner of a record, or any admin.

    Used for actions on tasks: a member may edit or delete tasks they
    own; admins may edit or delete any task.
    """
    if user.id == resource_owner_id or is_admin(user):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to act on this resource",
    )


def require_self_or_admin(user: models.User, target_user_id: int) -> None:
    """Allow a user acting on their own profile, or any admin.

    Used for profile updates: a member may edit their own profile but
    not anyone else\'s; admins may edit any profile.
    """
    if user.id == target_user_id or is_admin(user):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to act on this user",
    )
