"""Payments views (README Section 17, 25.1 & 26.1)."""

import csv
import datetime
import logging
from decimal import Decimal, InvalidOperation

import stripe
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers as drf_serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminOrHigher

from .filters import PaymentFilter
from .models import Payment, SalaryAuditLog, SalaryRecord
from .serializers import PaymentSerializer, SalaryRecordSerializer
from .services import record_payment
from .stripe_service import construct_webhook_event, process_webhook_event

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers — period parsing & branch scoping
# ---------------------------------------------------------------------------


def _parse_period(request) -> tuple[datetime.date, datetime.date]:
    """Parse ?period_start=&period_end= from the query string.

    Falls back to the **current calendar month** when either bound is
    missing — that is the canonical "this month's payroll" view.
    """
    today = datetime.date.today()
    raw_start = request.query_params.get("period_start")
    raw_end = request.query_params.get("period_end")

    def _parse(d):
        try:
            return datetime.date.fromisoformat(d)
        except (TypeError, ValueError):
            return None

    period_start = _parse(raw_start) or today.replace(day=1)
    if raw_end:
        period_end = _parse(raw_end) or today
    else:
        # Last day of the same month.
        if period_start.month == 12:
            next_month = period_start.replace(year=period_start.year + 1, month=1, day=1)
        else:
            next_month = period_start.replace(month=period_start.month + 1, day=1)
        period_end = next_month - datetime.timedelta(days=1)

    return period_start, period_end


def _scope_records_to_branch(qs, user, branch_id=None):
    """Filter SalaryRecord queryset to the user's branch (CEO sees all).

    SalaryRecord has no direct branch FK; we resolve it through whichever
    profile the account holds (staff / administrator / director).
    """
    from apps.accounts.branch_scope import get_user_branch

    user_branch = get_user_branch(user)  # None for SuperAdmin
    branch_pk = None
    if branch_id is not None:
        branch_pk = int(branch_id)
    elif user_branch is not None:
        branch_pk = user_branch.pk

    if branch_pk is None:
        return qs  # SuperAdmin without a branch filter — sees everything.

    return qs.filter(
        Q(account__staff_profile__branch_id=branch_pk)
        | Q(account__administrator_profile__branch_id=branch_pk)
        | Q(account__director_profile__branch_id=branch_pk)
    )


def _is_manager(user) -> bool:
    """Salary 'manager' = Director or SuperAdmin only.

    Administrators see their own salary like Staff (read-only) — they do not
    lock records, mark them paid, or view branch payroll roster.
    """
    return bool(
        getattr(user, "is_director", False)
        or getattr(user, "is_superadmin", False)
    )


def _account_name(acc) -> str:
    """Resolve a human label for an Account via its profile, then phone, then str."""
    for attr in ("director_profile", "administrator_profile", "staff_profile", "client_profile"):
        prof = getattr(acc, attr, None)
        name = getattr(prof, "full_name", None) if prof else None
        if name:
            return name
    return getattr(acc, "phone", None) or str(acc)


class SalaryRecordViewSet(viewsets.ModelViewSet):
    """Salary records — list / detail / calculate / mark-paid.

    Permission matrix:
        - Staff:        only their own records (read-only); may preview own salary.
        - Administrator/Director/SuperAdmin: branch-scoped roster + may
          calculate (lock) and mark records paid.
        - SuperAdmin (CEO): may pass ``?branch=<id>`` to scope.

    Filterable via ``?account=&status=&period_start=&period_end=&branch=``.
    """

    serializer_class = SalaryRecordSerializer
    permission_classes = [IsAuthenticated]
    ordering_fields = ["created_at", "period_start", "period_end", "amount", "status"]
    ordering = ["-period_end", "-created_at"]
    filterset_fields = ["account", "status", "period_start", "period_end"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = SalaryRecord.objects.select_related("account").all()
        user = self.request.user
        if not _is_manager(user):
            return qs.filter(account=user)
        return _scope_records_to_branch(
            qs, user, self.request.query_params.get("branch"),
        )

    # ---- Custom actions --------------------------------------------------

    @action(detail=False, methods=["get"], url_path="preview")
    def preview(self, request):
        """GET /payments/salary/preview/?account=&period_start=&period_end=

        Returns the live :class:`SalaryBreakdown` for the requested account
        + period **without persisting** it. Staff can only preview their own
        salary; Director/Admin/CEO may preview any branch employee.
        """
        from apps.accounts.models import Account
        from apps.staff.salary_service import calculate_salary_breakdown

        period_start, period_end = _parse_period(request)
        account_id = request.query_params.get("account")

        if account_id and _is_manager(request.user):
            try:
                account = Account.objects.get(pk=account_id)
            except Account.DoesNotExist:
                raise drf_serializers.ValidationError({"account": "Not found."})
            self._assert_branch_access(request.user, account)
        else:
            account = request.user

        breakdown = calculate_salary_breakdown(account.pk, period_start, period_end)
        return Response({
            "account": account.pk,
            "account_name": _account_name(account),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            **{k: str(v) if isinstance(v, Decimal) else v for k, v in breakdown.items()},
        })

    @action(detail=False, methods=["get"], url_path="roster")
    def roster(self, request):
        """GET /payments/salary/roster/?branch=&period_start=&period_end=

        Branch payroll roster — every staff/admin/director on that branch
        with their **live** computed salary for the period plus, when
        present, the matching persisted ``SalaryRecord`` (id + status).
        Manager-only.
        """
        from apps.accounts.branch_scope import get_user_branch
        from apps.accounts.models import Account
        from apps.staff.salary_service import calculate_salary_breakdown

        if not _is_manager(request.user):
            raise drf_serializers.ValidationError(
                {"detail": "Roster is only available to managers."}
            )

        period_start, period_end = _parse_period(request)
        user_branch = get_user_branch(request.user)
        branch_pk = None
        if user_branch is not None:
            branch_pk = user_branch.pk
        else:  # CEO
            raw = request.query_params.get("branch")
            if not raw:
                raise drf_serializers.ValidationError(
                    {"branch": "SuperAdmin must specify ?branch=<id>."}
                )
            branch_pk = int(raw)

        # All accounts that hold any role on the branch.
        accounts = (
            Account.objects
            .filter(
                Q(staff_profile__branch_id=branch_pk, staff_profile__is_active=True)
                | Q(administrator_profile__branch_id=branch_pk, administrator_profile__is_active=True)
                | Q(director_profile__branch_id=branch_pk, director_profile__is_active=True)
            )
            .select_related("staff_profile", "administrator_profile", "director_profile")
            .distinct()
        )

        existing_records = {
            (r.account_id, r.period_start, r.period_end): r
            for r in SalaryRecord.objects.filter(
                period_start=period_start,
                period_end=period_end,
                account__in=accounts,
            )
        }

        rows = []
        for acc in accounts:
            breakdown = calculate_salary_breakdown(acc.pk, period_start, period_end)
            persisted = existing_records.get((acc.pk, period_start, period_end))
            roles = []
            if getattr(acc, "director_profile", None):
                roles.append("Director")
            if getattr(acc, "administrator_profile", None):
                roles.append("Administrator")
            if getattr(acc, "staff_profile", None):
                roles.append("Staff")
            rows.append({
                "account": acc.pk,
                "account_name": _account_name(acc),
                "roles": roles,
                "shift_count": breakdown["shift_count"],
                "shift_pay": str(breakdown["shift_pay"]),
                "income_bonus": str(breakdown["income_bonus"]),
                "cleaning_bonus": str(breakdown["cleaning_bonus"]),
                "director_fixed": str(breakdown["director_fixed"]),
                "penalties": str(breakdown["penalties"]),
                "total": str(breakdown["total"]),
                "record_id": persisted.pk if persisted else None,
                "record_status": persisted.status if persisted else None,
            })

        # Sort: highest total first.
        rows.sort(key=lambda r: Decimal(r["total"]), reverse=True)

        # CSV export branch (README §3.1 — CEO can export CSV).
        # NOTE: we use ?export=csv (NOT ?format=csv) because DRF reserves the
        # ``format`` query param for content-negotiation and would 404 here.
        if (request.query_params.get("export") or "").lower() == "csv":
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = (
                f'attachment; filename="payroll_branch{branch_pk}_'
                f'{period_start.isoformat()}_{period_end.isoformat()}.csv"'
            )
            writer = csv.writer(response)
            writer.writerow([
                "Account", "Name", "Roles", "Shifts", "Shift pay",
                "Income bonus", "Cleaning bonus", "Director fixed",
                "Penalties", "Total", "Record ID", "Status",
            ])
            for r in rows:
                writer.writerow([
                    r["account"], r["account_name"], "; ".join(r["roles"]),
                    r["shift_count"], r["shift_pay"], r["income_bonus"],
                    r["cleaning_bonus"], r["director_fixed"], r["penalties"],
                    r["total"], r["record_id"] or "", r["record_status"] or "open",
                ])
            return response

        return Response({
            "branch": branch_pk,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "totals": {
                "headcount": len(rows),
                "payroll": str(sum((Decimal(r["total"]) for r in rows), Decimal("0"))),
                "locked": sum(1 for r in rows if r["record_id"] is not None),
                "paid": sum(1 for r in rows if r["record_status"] == "paid"),
            },
            "rows": rows,
        })

    @action(detail=False, methods=["get"], url_path="lifecycle-status")
    def lifecycle_status(self, request):
        """GET /payments/salary/lifecycle-status/

        Calendar-driven payroll button state for the Salary page.
        See REFACTOR_PLAN_2026_04 §3.3.
        """
        from .salary_lifecycle import lifecycle_status as _status
        return Response(_status())

    @action(detail=False, methods=["post"], url_path="pay-advance")
    def pay_advance(self, request):
        """POST /payments/salary/pay-advance/

        Body: ``{year, month}``. CEO-only, day 15–20 only.
        Bulk-creates ``SalaryRecord(kind=advance)`` for every active employee.
        """
        from .salary_lifecycle import WindowError, pay_advance as _do_pay
        if not request.user.is_superadmin:
            raise drf_serializers.ValidationError(
                {"detail": "Only the CEO can pay advances."}
            )
        try:
            year = int(request.data.get("year"))
            month = int(request.data.get("month"))
        except (TypeError, ValueError):
            raise drf_serializers.ValidationError(
                {"detail": "year and month are required integers."}
            )
        try:
            records = _do_pay(actor=request.user, year=year, month=month)
        except WindowError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(
            {
                "created": len(records),
                "records": SalaryRecordSerializer(records, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="pay-final")
    def pay_final(self, request):
        """POST /payments/salary/pay-final/

        Body: ``{year, month}`` — the month being paid (M). CEO-only,
        day 1–5 of M+1 only. Per Q6 the amount is always
        ``full_salary − sum(advances)``; if no advance row exists this
        equals the full salary.
        """
        from .salary_lifecycle import WindowError, pay_final as _do_pay
        if not request.user.is_superadmin:
            raise drf_serializers.ValidationError(
                {"detail": "Only the CEO can pay the final salary."}
            )
        try:
            year = int(request.data.get("year"))
            month = int(request.data.get("month"))
        except (TypeError, ValueError):
            raise drf_serializers.ValidationError(
                {"detail": "year and month are required integers."}
            )
        try:
            records = _do_pay(actor=request.user, year=year, month=month)
        except WindowError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(
            {
                "created": len(records),
                "records": SalaryRecordSerializer(records, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="pay-late")
    def pay_late(self, request):
        """POST /payments/salary/pay-late/

        Body: ``{year, month, reason}`` — Q11 manual late-payment recovery.
        CEO-only, written reason mandatory, audit-logged.
        """
        from .salary_lifecycle import WindowError, pay_late as _do_pay
        if not request.user.is_superadmin:
            raise drf_serializers.ValidationError(
                {"detail": "Only the CEO can record late salary payments."}
            )
        try:
            year = int(request.data.get("year"))
            month = int(request.data.get("month"))
        except (TypeError, ValueError):
            raise drf_serializers.ValidationError(
                {"detail": "year and month are required integers."}
            )
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            raise drf_serializers.ValidationError(
                {"reason": "A written reason is required."}
            )
        try:
            records = _do_pay(actor=request.user, year=year, month=month,
                              reason=reason)
        except WindowError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except ValueError as exc:
            raise drf_serializers.ValidationError({"detail": str(exc)})
        return Response(
            {
                "created": len(records),
                "records": SalaryRecordSerializer(records, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="calculate")
    def calculate(self, request):
        """POST /payments/salary/calculate/

        Body: ``{account, period_start, period_end}``. Persists a new
        ``SalaryRecord`` (or returns the existing one if already locked).
        Manager-only.
        """
        from apps.accounts.models import Account
        from apps.staff.salary_service import calculate_salary

        if not _is_manager(request.user):
            raise drf_serializers.ValidationError(
                {"detail": "Only managers may lock payroll records."}
            )

        account_id = request.data.get("account")
        try:
            account = Account.objects.get(pk=account_id)
        except (Account.DoesNotExist, ValueError, TypeError):
            raise drf_serializers.ValidationError({"account": "Account not found."})

        self._assert_branch_access(request.user, account)

        try:
            period_start = datetime.date.fromisoformat(request.data.get("period_start", ""))
            period_end = datetime.date.fromisoformat(request.data.get("period_end", ""))
        except (TypeError, ValueError):
            raise drf_serializers.ValidationError(
                {"detail": "period_start and period_end (YYYY-MM-DD) are required."}
            )
        if period_end < period_start:
            raise drf_serializers.ValidationError(
                {"detail": "period_end must be on/after period_start."}
            )
        # Future-period guard — no shift data exists yet, locking it would
        # persist a meaningless zero-row that blocks the real cron lock later.
        today = datetime.date.today()
        if period_start > today:
            raise drf_serializers.ValidationError(
                {"detail": "Cannot lock a payroll period that hasn't started yet."}
            )

        existing = SalaryRecord.objects.filter(
            account=account, period_start=period_start, period_end=period_end,
        ).first()
        if existing:
            return Response(SalaryRecordSerializer(existing).data, status=status.HTTP_200_OK)

        record = calculate_salary(account.pk, period_start, period_end)
        SalaryAuditLog.objects.create(
            record=record,
            actor=request.user,
            action=SalaryAuditLog.Action.CALCULATED,
            before_amount=None,
            after_amount=record.amount,
            note=f"Locked period {period_start.isoformat()} → {period_end.isoformat()}",
        )
        return Response(SalaryRecordSerializer(record).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request, pk=None):
        """POST /payments/salary/{id}/mark-paid/ — flip a record to ``paid``.

        Manager-only, branch-scoped (the existing ``get_queryset`` already
        prevents managers from touching another branch's records).

        Side effects:
            * Writes a :class:`SalaryAuditLog` entry.
            * Fires an in-app + Telegram notification to the recipient
              (README §10, §26.4).
        """
        if not _is_manager(request.user):
            raise drf_serializers.ValidationError(
                {"detail": "Only managers may mark salaries as paid."}
            )
        record = self.get_object()
        if record.status == SalaryRecord.SalaryStatus.PAID:
            return Response(SalaryRecordSerializer(record).data)
        record.status = SalaryRecord.SalaryStatus.PAID
        record.save(update_fields=["status", "updated_at"])

        SalaryAuditLog.objects.create(
            record=record,
            actor=request.user,
            action=SalaryAuditLog.Action.MARKED_PAID,
            before_amount=record.amount,
            after_amount=record.amount,
            note="Marked paid",
        )

        # Notify the recipient (in-app + Telegram).
        try:
            from apps.reports.models import Notification as _Notif
            from apps.reports.services import send_notification
            send_notification(
                account_id=record.account_id,
                notification_type=_Notif.NotificationType.PAYMENT,
                message=(
                    f"Your salary for "
                    f"{record.period_start.isoformat()} — {record.period_end.isoformat()} "
                    f"({record.amount} UZS) has been paid."
                ),
            )
        except Exception:
            logger.exception("Salary payout notification failed for record #%s", record.pk)

        return Response(SalaryRecordSerializer(record).data)

    @action(detail=True, methods=["patch"], url_path="override")
    def override(self, request, pk=None):
        """PATCH /payments/salary/{id}/override/

        Body: ``{amount: <decimal>, note?: <str>}``. Allows a Director or
        SuperAdmin to manually adjust a locked record's amount (e.g. cash
        reconciliation tweak). Always audited (README §3.1).

        Cannot override an already-paid record — those are sealed.
        """
        if not _is_manager(request.user):
            raise drf_serializers.ValidationError(
                {"detail": "Only managers may override payroll."}
            )
        record = self.get_object()
        if record.status == SalaryRecord.SalaryStatus.PAID:
            raise drf_serializers.ValidationError(
                {"detail": "Paid records are sealed and cannot be overridden."}
            )

        raw_amount = request.data.get("amount")
        try:
            new_amount = Decimal(str(raw_amount))
        except (InvalidOperation, TypeError):
            raise drf_serializers.ValidationError({"amount": "Must be a decimal value."})
        if new_amount < 0:
            raise drf_serializers.ValidationError({"amount": "Cannot be negative."})

        before = record.amount
        record.amount = new_amount
        record.save(update_fields=["amount", "updated_at"])

        SalaryAuditLog.objects.create(
            record=record,
            actor=request.user,
            action=SalaryAuditLog.Action.OVERRIDDEN,
            before_amount=before,
            after_amount=new_amount,
            note=str(request.data.get("note") or "")[:255],
        )
        return Response(SalaryRecordSerializer(record).data)

    @action(detail=True, methods=["get"], url_path="audit")
    def audit(self, request, pk=None):
        """GET /payments/salary/{id}/audit/ — chronological audit trail."""
        record = self.get_object()
        logs = record.audit_logs.select_related("actor").all()
        return Response([
            {
                "id": log.pk,
                "action": log.action,
                "actor": log.actor_id,
                "actor_name": _account_name(log.actor) if log.actor else "System",
                "before_amount": str(log.before_amount) if log.before_amount is not None else None,
                "after_amount": str(log.after_amount) if log.after_amount is not None else None,
                "note": log.note,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ])

    # ---- Internal helpers -------------------------------------------------

    def _assert_branch_access(self, user, target_account):
        """Director/Admin may only act on their own branch's accounts."""
        from apps.accounts.branch_scope import get_user_branch
        from rest_framework.exceptions import PermissionDenied

        user_branch = get_user_branch(user)
        if user_branch is None:
            return  # SuperAdmin
        for attr in ("staff_profile", "administrator_profile", "director_profile"):
            profile = getattr(target_account, attr, None)
            if profile is not None and profile.branch_id == user_branch.pk:
                return
        raise PermissionDenied("This account is not on your branch.")


class PaymentViewSet(viewsets.ModelViewSet):
    """CRUD for payments.

    - Admin / Director / SuperAdmin can create and view payments.
    - Staff and Clients have no payment management access.

    Create is fully delegated to the service layer which enforces:
        - idempotency (no double payment)
        - booking status transitions (pending → paid)
    """

    queryset = Payment.objects.select_related(
        "booking", "booking__client", "booking__room", "created_by",
    )
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsAdminOrHigher]
    filterset_class = PaymentFilter
    ordering_fields = ["amount", "is_paid", "payment_type", "created_at", "paid_at"]
    ordering = ["-created_at"]
    search_fields = ["booking__client__full_name", "payment_intent_id"]

    def perform_create(self, serializer):
        """Delegate creation to the service layer."""
        from django.core.exceptions import ValidationError as DjangoValidationError
        from rest_framework.exceptions import ValidationError as DRFValidationError

        data = serializer.validated_data
        try:
            payment = record_payment(
                booking=data["booking"],
                amount=data["amount"],
                payment_type=data["payment_type"],
                method=data.get("method") or "cash",
                # Service resolves Account → Administrator transparently.
                created_by=data.get("created_by") or self.request.user,
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(
                getattr(exc, "message_dict", None) or {"detail": exc.messages}
            )
        serializer.instance = payment


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    """
    Stripe webhook receiver (README Section 26.1).

    URL: POST /api/v1/payments/webhook/

    Security:
        - CSRF exempt (external caller)
        - No authentication (Stripe sends raw POST)
        - Signature verified via ``STRIPE_WEBHOOK_SECRET``

    Handled events:
        - ``payment_intent.succeeded``  → mark booking as paid
        - ``payment_intent.payment_failed`` → log failure
    """

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        if not sig_header:
            return JsonResponse(
                {"error": "Missing Stripe-Signature header."},
                status=400,
            )

        # Verify signature
        try:
            event = construct_webhook_event(payload, sig_header)
        except stripe.error.SignatureVerificationError:
            logger.warning("Stripe webhook: invalid signature.")
            return JsonResponse(
                {"error": "Invalid signature."},
                status=400,
            )
        except ValueError:
            logger.warning("Stripe webhook: invalid payload.")
            return JsonResponse(
                {"error": "Invalid payload."},
                status=400,
            )

        # Process (idempotent)
        was_new = process_webhook_event(event)

        return JsonResponse(
            {
                "status": "ok",
                "event_id": event.id,
                "new": was_new,
            },
            status=200,
        )
