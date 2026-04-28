"""Helpers for restricting querysets and writes to a user's branch.

Business rule (README §3):
    - SuperAdmin (CEO): sees ALL branches; may pass ``?branch=<id>`` to scope.
    - Director: pinned to a single branch (their ``director_profile.branch``).
    - Administrator: pinned to a single branch (``administrator_profile.branch``).
    - Staff: pinned to their branch via ``staff_profile.branch``.
    - Client: not allowed in admin views.

Use these helpers from any ``ModelViewSet`` that holds branch-scoped data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from rest_framework.exceptions import PermissionDenied, ValidationError

if TYPE_CHECKING:
    from apps.branches.models import Branch


def get_user_branch(user) -> Optional["Branch"]:
    """Return the Branch instance pinned to the user, or ``None`` for SuperAdmin.

    Raises ``PermissionDenied`` for any account without a branch-scoped profile
    (e.g. a Client trying to reach an admin endpoint).
    """
    if not user or not user.is_authenticated:
        raise PermissionDenied("Authentication required.")
    if user.is_superadmin:
        return None  # CEO — sees everything
    for attr in ("director_profile", "administrator_profile", "staff_profile"):
        profile = getattr(user, attr, None)
        if profile is not None and getattr(profile, "branch", None) is not None:
            return profile.branch
    raise PermissionDenied("This account has no branch assignment.")


def scope_queryset_by_branch(qs, user, branch_field: str = "branch"):
    """Filter ``qs`` to the user's branch (no-op for SuperAdmin).

    The ``branch_field`` argument is the lookup path to the FK on the model
    (defaults to ``"branch"``; pass ``"room__branch"`` if the model has no
    direct branch FK, etc.).
    """
    branch = get_user_branch(user)
    if branch is None:
        return qs  # SuperAdmin sees all
    return qs.filter(**{branch_field: branch})


def enforce_branch_on_create(user, supplied_branch, *, allow_override: bool = False) -> "Branch":
    """Validate / coerce the ``branch`` value used at create-time.

    For non-SuperAdmin users the branch is forced to the user's pinned branch;
    any mismatch is treated as a 400 (the frontend is expected to send the
    correct one, but we never trust client input on a security boundary).

    For SuperAdmin a branch must be supplied (CEO must explicitly pick one).

    Returns the Branch instance that should be stored on the new row.
    """
    user_branch = get_user_branch(user)

    if user_branch is None:
        # SuperAdmin path — must explicitly choose a branch.
        if supplied_branch is None:
            raise ValidationError(
                {"branch": "SuperAdmin must select a branch when creating this resource."}
            )
        return supplied_branch  # type: ignore[return-value]

    # Director / Admin path — pinned to their own branch.
    if supplied_branch is None:
        return user_branch
    supplied_pk = getattr(supplied_branch, "pk", supplied_branch)
    if supplied_pk != user_branch.pk:
        if allow_override:
            return supplied_branch  # type: ignore[return-value]
        raise PermissionDenied(
            "You can only create resources for your own branch."
        )
    return user_branch
