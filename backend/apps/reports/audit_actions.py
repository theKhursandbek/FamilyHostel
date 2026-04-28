"""
Centralised audit-log action constants.

Every state-changing service call writes an :class:`AuditLog` row whose
``action`` field is one of the strings defined here. Keeping them in a single
module avoids typos, makes the catalogue searchable, and lets us power the
ActivityLogPage filter dropdown from a known set.

The naming convention is ``<entity>.<verb>`` — both lowercase, dot-separated,
underscores within either segment. Generic CRUD verbs are ``created``,
``updated``, ``deleted``; everything else describes a domain transition
(``approved``, ``paid``, ``handover`` …).

Some action codes are produced dynamically (e.g. ``salary_adjustment.<kind>_created``
or ``cash_session.<decision>``). For those we expose a small helper at the
bottom of the module rather than enumerating every variant.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
ACCOUNT_CREATED = "account.created"
ACCOUNT_UPDATED = "account.updated"
ACCOUNT_DELETED = "account.deleted"
ACCOUNT_DISABLED = "account.disabled"
ACCOUNT_ENABLED = "account.enabled"
ACCOUNT_DUAL_ROLE_COLLAPSED = "accounts.dual_role_collapsed"

# Implicit "client signed up via booking" path (apps.bookings.services).
CLIENT_CREATED = "client.created"

# ---------------------------------------------------------------------------
# Branches / inventory
# ---------------------------------------------------------------------------
BRANCH_CREATED = "branch.created"
BRANCH_UPDATED = "branch.updated"
BRANCH_DELETED = "branch.deleted"
ROOMTYPE_CREATED = "roomtype.created"
ROOMTYPE_UPDATED = "roomtype.updated"
ROOMTYPE_DELETED = "roomtype.deleted"
ROOM_CREATED = "room.created"
ROOM_UPDATED = "room.updated"
ROOM_DELETED = "room.deleted"

# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------
BOOKING_CREATED = "booking.created"
BOOKING_CANCELED = "booking.canceled"
BOOKING_COMPLETED = "booking.completed"
BOOKING_EXTENDED = "booking.extended"

# ---------------------------------------------------------------------------
# Payments / Stripe / salary lifecycle
# ---------------------------------------------------------------------------
PAYMENT_RECORDED = "payment.recorded"
PAYMENT_REFUNDED = "payment.refunded"

STRIPE_PAYMENT_INTENT_CREATED = "stripe.payment_intent_created"
STRIPE_PAYMENT_SUCCEEDED = "stripe.payment_succeeded"
STRIPE_PAYMENT_FAILED = "stripe.payment_failed"

SALARY_ADVANCE_PAID = "salary.advance_paid"
SALARY_FINAL_PAID = "salary.final_paid"
SALARY_PAID_LATE = "salary.paid_late"

# ---------------------------------------------------------------------------
# Penalties / facility / monthly reports
# ---------------------------------------------------------------------------
PENALTY_CREATED = "penalty.created"
PENALTY_UPDATED = "penalty.updated"
PENALTY_DELETED = "penalty.deleted"

FACILITY_LOG_REQUESTED = "facility_log.requested"
FACILITY_LOG_UPDATED = "facility_log.updated"
FACILITY_LOG_APPROVED = "facility_log.approved"
FACILITY_LOG_REJECTED = "facility_log.rejected"
FACILITY_LOG_PAID = "facility_log.paid"
FACILITY_LOG_RESOLVED = "facility_log.resolved"

MONTHLY_REPORT_GENERATED = "monthly_report.generated"

# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------
CLEANING_TASK_CREATED = "cleaning_task.created"
CLEANING_TASK_ASSIGNED = "cleaning_task.assigned"
CLEANING_TASK_DIRECTOR_ASSIGNED = "cleaning_task.director_assigned"
CLEANING_TASK_COMPLETED = "cleaning_task.completed"
CLEANING_TASK_RETRIED = "cleaning_task.retried"
CLEANING_TASK_OVERRIDDEN = "cleaning_task.overridden"
CLEANING_TASK_DELETED = "cleaning_task.deleted"

# ---------------------------------------------------------------------------
# Staff (attendance / shifts / day-off)
# ---------------------------------------------------------------------------
ATTENDANCE_CHECK_IN = "attendance.check_in"
ATTENDANCE_CHECK_OUT = "attendance.check_out"
SHIFT_ASSIGNED = "shift.assigned"
DAY_OFF_REQUEST_CREATED = "day_off_request.created"
DAY_OFF_REQUEST_APPROVED = "day_off_request.approved"
DAY_OFF_REQUEST_REJECTED = "day_off_request.rejected"

# ---------------------------------------------------------------------------
# Admin panel — cash sessions, room inspections
# ---------------------------------------------------------------------------
ROOM_INSPECTION_CREATED = "room_inspection.created"
CASH_SESSION_OPENED = "cash_session.opened"
CASH_SESSION_CLOSED = "cash_session.closed"
CASH_SESSION_HANDOVER = "cash_session.handover"
CASH_SESSION_ACCEPTED = "cash_session.accepted"
CASH_SESSION_DISPUTED = "cash_session.disputed"


# ---------------------------------------------------------------------------
# Dynamic helpers
# ---------------------------------------------------------------------------
def salary_adjustment_action(kind: str, verb: str) -> str:
    """Return ``salary_adjustment.<kind>_<verb>`` (e.g. ``bonus_created``)."""
    return f"salary_adjustment.{kind}_{verb}"


def cash_session_decision_action(decision: str) -> str:
    """Return ``cash_session.<decision>`` for variance-review decisions."""
    return f"cash_session.{decision}"


# ---------------------------------------------------------------------------
# Catalogue — every static action defined above.
# Used by the SuperAdmin ActivityLogPage to populate the search dropdown.
# Dynamic actions (salary adjustments, cash session decisions) are appended
# at runtime by the AuditLogViewSet facets endpoint, which reads distinct
# values from the DB.
# ---------------------------------------------------------------------------
ALL_ACTIONS: tuple[str, ...] = (
    ACCOUNT_CREATED, ACCOUNT_UPDATED, ACCOUNT_DELETED,
    ACCOUNT_DISABLED, ACCOUNT_ENABLED, ACCOUNT_DUAL_ROLE_COLLAPSED,
    CLIENT_CREATED,
    BRANCH_CREATED, BRANCH_UPDATED, BRANCH_DELETED,
    ROOMTYPE_CREATED, ROOMTYPE_UPDATED, ROOMTYPE_DELETED,
    ROOM_CREATED, ROOM_UPDATED, ROOM_DELETED,
    BOOKING_CREATED, BOOKING_CANCELED, BOOKING_COMPLETED, BOOKING_EXTENDED,
    PAYMENT_RECORDED, PAYMENT_REFUNDED,
    STRIPE_PAYMENT_INTENT_CREATED, STRIPE_PAYMENT_SUCCEEDED, STRIPE_PAYMENT_FAILED,
    SALARY_ADVANCE_PAID, SALARY_FINAL_PAID, SALARY_PAID_LATE,
    PENALTY_CREATED, PENALTY_UPDATED, PENALTY_DELETED,
    FACILITY_LOG_REQUESTED, FACILITY_LOG_UPDATED,
    FACILITY_LOG_APPROVED, FACILITY_LOG_REJECTED,
    FACILITY_LOG_PAID, FACILITY_LOG_RESOLVED,
    MONTHLY_REPORT_GENERATED,
    CLEANING_TASK_CREATED, CLEANING_TASK_ASSIGNED, CLEANING_TASK_DIRECTOR_ASSIGNED,
    CLEANING_TASK_COMPLETED, CLEANING_TASK_RETRIED, CLEANING_TASK_OVERRIDDEN,
    CLEANING_TASK_DELETED,
    ATTENDANCE_CHECK_IN, ATTENDANCE_CHECK_OUT, SHIFT_ASSIGNED,
    DAY_OFF_REQUEST_CREATED, DAY_OFF_REQUEST_APPROVED, DAY_OFF_REQUEST_REJECTED,
    ROOM_INSPECTION_CREATED,
    CASH_SESSION_OPENED, CASH_SESSION_CLOSED, CASH_SESSION_HANDOVER,
    CASH_SESSION_ACCEPTED, CASH_SESSION_DISPUTED,
)
