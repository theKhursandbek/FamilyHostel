"""
Role-based permission classes for the Hostel Management System.

Permission matrix (README Section 18):
    ┌────────────────────┬───────┬───────┬──────────┬─────────────┐
    │ Action             │ Staff │ Admin │ Director │ Super Admin │
    ├────────────────────┼───────┼───────┼──────────┼─────────────┤
    │ View rooms         │  ✅   │  ✅   │   ✅     │     ✅      │
    │ Create booking     │  ❌   │  ✅   │   ✅     │     ✅      │
    │ Apply discount     │  ❌   │  ✅   │   ✅     │     ✅      │
    │ Change price       │  ❌   │  ❌   │   ❌     │     ✅      │
    │ Assign shifts      │  ❌   │  ❌   │   ✅     │     ✅      │
    │ Approve days off   │  ❌   │  ❌   │   ✅     │     ✅      │
    │ Upload cleaning    │  ✅   │  ❌   │   ❌     │     ❌      │
    │ Override AI        │  ❌   │  ❌   │   ✅     │     ✅      │
    │ View reports       │  ❌   │  ✅   │   ✅     │     ✅      │
    │ Export CSV         │  ❌   │  ❌   │   ❌     │     ✅      │
    └────────────────────┴───────┴───────┴──────────┴─────────────┘

Role hierarchy (highest → lowest):
    SuperAdmin > Director > Administrator > Staff > Client

Usage in ViewSets:
    permission_classes = [IsAuthenticated, IsAdminOrHigher]
    permission_classes = [IsAuthenticated, IsDirectorOrHigher]
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

__all__ = [
    # Atomic role checks
    "IsSuperAdmin",
    "IsDirector",
    "IsAdministrator",
    "IsStaff",
    "IsClient",
    # Hierarchical (role OR above)
    "IsDirectorOrHigher",
    "IsAdminOrHigher",
    "IsStaffOrHigher",
    "IsAnyRole",
    # Helpers
    "ReadOnly",
]


# ==============================================================================
# HELPERS
# ==============================================================================


def _has_role(user, role_attr: str) -> bool:
    """Check a role via the Account model's ``is_<role>`` properties."""
    return bool(
        user
        and user.is_authenticated
        and getattr(user, role_attr, False)
    )


class ReadOnly(BasePermission):
    """Allow any authenticated user to perform safe (read-only) methods."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return request.method in ("GET", "HEAD", "OPTIONS")


# ==============================================================================
# ATOMIC ROLE PERMISSIONS
# ==============================================================================


class IsSuperAdmin(BasePermission):
    """
    Allow access only to Super Admin accounts.

    Checks ``Account.is_superadmin`` property (role table lookup).
    """

    message = "Super Admin access required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return _has_role(request.user, "is_superadmin")


class IsDirector(BasePermission):
    """
    Allow access only to Director accounts.

    Checks ``Account.is_director`` property (role table lookup).
    """

    message = "Director access required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return _has_role(request.user, "is_director")


class IsAdministrator(BasePermission):
    """
    Allow access only to Administrator accounts.

    Checks ``Account.is_administrator`` property (role table lookup).
    """

    message = "Administrator access required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return _has_role(request.user, "is_administrator")


class IsStaff(BasePermission):
    """
    Allow access only to Staff (cleaning worker) accounts.

    Checks ``Account.is_hostel_staff`` property (role table lookup).
    Note: This is NOT Django's built-in ``is_staff`` flag.
    """

    message = "Staff access required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return _has_role(request.user, "is_hostel_staff")


class IsClient(BasePermission):
    """
    Allow access only to Client accounts.

    Checks ``Account.is_client`` property (role table lookup).
    """

    message = "Client access required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return _has_role(request.user, "is_client")


# ==============================================================================
# HIERARCHICAL PERMISSIONS (role OR higher)
# ==============================================================================


class IsDirectorOrHigher(BasePermission):
    """
    Director or Super Admin.

    Covers: assign shifts, approve days off, override AI, cancel bookings.
    """

    message = "Director or Super Admin access required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return (
            _has_role(user, "is_superadmin")
            or _has_role(user, "is_director")
        )


class IsAdminOrHigher(BasePermission):
    """
    Administrator, Director, or Super Admin.

    Covers: create booking, apply discount, view reports, manage rooms.
    """

    message = "Administrator, Director, or Super Admin access required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return (
            _has_role(user, "is_superadmin")
            or _has_role(user, "is_director")
            or _has_role(user, "is_administrator")
        )


class IsStaffOrHigher(BasePermission):
    """
    Staff, Administrator, Director, or Super Admin.

    Covers: any internal team member (excludes clients).
    """

    message = "Internal team access required (Staff or above)."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return (
            _has_role(user, "is_superadmin")
            or _has_role(user, "is_director")
            or _has_role(user, "is_administrator")
            or _has_role(user, "is_hostel_staff")
        )


class IsAnyRole(BasePermission):
    """
    Any authenticated user with at least one assigned role.

    Prevents bare accounts (registered but unassigned) from accessing
    protected endpoints.
    """

    message = "You must have an assigned role to access this resource."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "roles", None)
        )


# ==============================================================================
# OBJECT-LEVEL PERMISSIONS
# ==============================================================================


class IsOwnerOrDirectorOrHigher(BasePermission):
    """
    Object-level: allow access if the requesting user owns the record
    OR is Director / Super Admin.

    The owning field is determined by ``owner_field`` on the view
    (default: ``"account"``).

    Usage::

        class AttendanceViewSet(viewsets.ModelViewSet):
            owner_field = "account"   # FK field pointing to Account
            permission_classes = [IsAuthenticated, IsOwnerOrDirectorOrHigher]
    """

    message = "You can only access your own records."

    def has_object_permission(
        self, request: Request, view: APIView, obj: object,
    ) -> bool:
        # Directors and Super Admins always pass
        user = request.user
        if _has_role(user, "is_superadmin") or _has_role(user, "is_director"):
            return True

        # Otherwise, check ownership
        owner_field: str = getattr(view, "owner_field", "account")
        owner = getattr(obj, owner_field, None)
        if owner is None:
            return False

        # The FK may point to the Account directly or to a related object
        owner_id = owner.pk if hasattr(owner, "pk") else owner
        return user.pk == owner_id


class IsAssignedStaffOrDirectorOrHigher(BasePermission):
    """
    Object-level: Staff can only access cleaning tasks assigned to them.
    Director / Super Admin can access any task.

    Usage::

        class CleaningTaskViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, IsAssignedStaffOrDirectorOrHigher]
    """

    message = "You can only access tasks assigned to you."

    def has_object_permission(
        self, request: Request, view: APIView, obj: object,
    ) -> bool:
        user = request.user

        # Directors and Super Admins always pass
        if _has_role(user, "is_superadmin") or _has_role(user, "is_director"):
            return True

        # Admins can view cleaning tasks (read-only)
        if _has_role(user, "is_administrator") and request.method in (
            "GET", "HEAD", "OPTIONS",
        ):
            return True

        # Staff can only access their own assigned tasks, or unassigned
        # tasks (so they can self-assign).
        if _has_role(user, "is_hostel_staff"):
            assigned_to = getattr(obj, "assigned_to", None)
            if assigned_to is None:
                return True  # unassigned — staff can pick it
            staff_profile = getattr(user, "staff_profile", None)
            return staff_profile is not None and staff_profile.pk == assigned_to.pk

        return False
