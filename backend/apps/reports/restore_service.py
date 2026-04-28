"""
Action-level **undo / redo** for :class:`apps.reports.models.AuditLog` rows.

This service interprets an audit row and re-applies the inverse (undo) or
re-applies the original change (redo) directly on the live entity. It is the
heart of the Live Activity restore feature.

Design overview
---------------

* **State of an audit row**: an audit row is either *active* (its action has
  been applied and not yet reverted) or *undone* (its action has been
  reverted by a later restore). This is tracked by querying for the most
  recent audit row whose ``after_data._undo_of == <row.pk>``:

  * no such row → *active*
  * latest such row's action ends with ``.undone`` → *undone*
  * latest such row's action ends with ``.redone`` → *active*

* **Conflict detection**: undo refuses to proceed when a *newer* audit row
  exists for the same ``(entity_type, entity_id)`` whose action represents a
  user-driven change (created/updated/deleted/etc., not undo/redo metadata).
  This prevents clobbering subsequent changes the operator may have forgotten.

* **Action coverage**: handles audit rows produced by
  :class:`apps.reports.audit_mixin.AuditedModelViewSetMixin` (dotted
  ``<entity>.<verb>`` codes) using the ``_raw`` payload embedded in
  ``before_data`` / ``after_data``. Legacy snake_case actions
  (``create_income_rule``, ``update_system_settings``, ``override:…``,
  ``set_salary:…``) are mapped onto the same handlers.

* **Atomicity**: each restore runs inside ``transaction.atomic`` and writes
  exactly one new ``AuditLog`` row tagged ``<original_action>.undone`` or
  ``.redone`` with ``after_data._undo_of`` referencing the source pk.
"""
from __future__ import annotations

import decimal as _decimal
import logging
from dataclasses import dataclass
from typing import Any

from django.apps import apps
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, RestrictedError

from .models import AuditLog
from .services import log_action

logger = logging.getLogger(__name__)


__all__ = [
    "RestoreService",
    "RestoreError",
    "RestoreConflictError",
    "NotReversibleError",
    "RestoreResult",
]

# Audit-action suffixes appended when an action is restored. Centralised
# here so the literals don't drift between query filters and exclude clauses.
_UNDONE_SUFFIX = ".undone"
_REDONE_SUFFIX = ".redone"

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class RestoreError(Exception):
    """Base class for restore failures."""


class NotReversibleError(RestoreError):
    """Raised when the audit row represents a non-reversible action."""


class RestoreConflictError(RestoreError):
    """Raised when newer changes block the restore."""


# ---------------------------------------------------------------------------
# Entity registry — maps audit ``entity_type`` → Django model class.
# Add new entries here when introducing audited models.
# ---------------------------------------------------------------------------
_ENTITY_REGISTRY: dict[str, str] = {
    "Account": "accounts.Account",
    "Branch": "branches.Branch",
    "Room": "branches.Room",
    "RoomType": "branches.RoomType",
    "RoomImage": "branches.RoomImage",
    "IncomeRule": "payments.IncomeRule",
    "SystemSettings": "admin_panel.SystemSettings",
    "Penalty": "reports.Penalty",
}


# Action codes that this service knows how to reverse.  Anything outside this
# set surfaces as :class:`NotReversibleError` so the UI can hide / disable the
# Undo button.
_REVERSIBLE_VERBS = {"created", "updated", "deleted", "enabled", "disabled"}
_LEGACY_ACTION_MAP: dict[str, tuple[str, str]] = {
    # legacy_code → (entity_type, verb)
    "create_income_rule": ("IncomeRule", "created"),
    "update_income_rule": ("IncomeRule", "updated"),
    "delete_income_rule": ("IncomeRule", "deleted"),
    "update_system_settings": ("SystemSettings", "updated"),
}


# ---------------------------------------------------------------------------
# Result envelope
# ---------------------------------------------------------------------------
@dataclass
class RestoreResult:
    direction: str  # "undo" | "redo"
    audit_id: int
    audit_action: str
    entity_type: str
    entity_id: int | None
    new_audit_id: int
    summary: str


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class RestoreService:
    """Apply undo / redo for a given :class:`AuditLog` row."""

    def __init__(self, *, actor=None) -> None:
        self.actor = actor

    # -- public API ----------------------------------------------------
    def undo(self, audit: AuditLog) -> RestoreResult:
        return self._apply(audit, direction="undo")

    def redo(self, audit: AuditLog) -> RestoreResult:
        return self._apply(audit, direction="redo")

    # -- helpers -------------------------------------------------------
    @staticmethod
    def parse_action(action: str) -> tuple[str | None, str | None]:
        """Return ``(entity_type, verb)`` or ``(None, None)`` if unknown."""
        if not action:
            return None, None
        if action in _LEGACY_ACTION_MAP:
            return _LEGACY_ACTION_MAP[action]
        if "." in action:
            prefix, _, verb = action.rpartition(".")
            # tolerate metadata suffixes (.undone / .redone shouldn't be re-applied)
            if verb in {"undone", "redone"}:
                return None, None
            entity_type = _PREFIX_TO_ENTITY.get(prefix.lower())
            return entity_type, verb
        return None, None

    @staticmethod
    def is_reversible(audit: AuditLog) -> bool:
        entity_type, verb = RestoreService.parse_action(audit.action)
        return bool(
            entity_type
            and verb in _REVERSIBLE_VERBS
            and entity_type in _ENTITY_REGISTRY
        )

    @staticmethod
    def state_of(audit: AuditLog) -> str:
        """Return ``"active"`` or ``"undone"``."""
        from django.db.utils import NotSupportedError

        try:
            latest = (
                AuditLog.objects.filter(after_data__contains={"_undo_of": audit.pk})
                .order_by("-created_at")
                .first()
            )
        except NotSupportedError:
            # SQLite (used in tests) doesn't support JSONField contains
            # lookups. Fall back to a Python-side scan over recent rows.
            latest = None
            for row in AuditLog.objects.filter(
                action__endswith=_UNDONE_SUFFIX,
            ).order_by("-created_at")[:50]:
                data = row.after_data or {}
                if isinstance(data, dict) and data.get("_undo_of") == audit.pk:
                    latest = row
                    break
        if latest is None:
            return "active"
        return "undone" if latest.action.endswith(".undone") else "active"

    # -- internal ------------------------------------------------------
    def _apply(self, audit: AuditLog, *, direction: str) -> RestoreResult:
        if not self.is_reversible(audit):
            raise NotReversibleError(
                f"Action '{audit.action}' is not reversible.",
            )

        entity_type, verb = self.parse_action(audit.action)
        assert entity_type is not None and verb is not None  # guarded above

        current_state = self.state_of(audit)
        if direction == "undo" and current_state == "undone":
            raise RestoreConflictError("This action is already undone.")
        if direction == "redo" and current_state == "active":
            raise RestoreConflictError("This action is currently active — nothing to redo.")

        self._guard_no_newer_changes(audit, entity_type)

        with transaction.atomic():
            try:
                summary = self._dispatch(audit, entity_type, verb, direction)
            except (ProtectedError, RestrictedError) as exc:
                # FK guards on related rows — e.g. trying to delete a Branch
                # that still owns Rooms.  Surface a friendly message instead
                # of bubbling up a generic 500.
                names = _describe_protected(exc)
                raise RestoreConflictError(
                    f"Cannot {direction} — dependent records still reference this "
                    f"{entity_type}: {names}. Remove or undo those first.",
                ) from exc
            except IntegrityError as exc:
                raise RestoreError(f"Database integrity error: {exc}") from exc
            new_audit = log_action(
                account=self.actor,
                action=f"{audit.action}.{'undone' if direction == 'undo' else 'redone'}",
                entity_type=entity_type,
                entity_id=audit.entity_id,
                before_data={"_summary": summary, "source_action": audit.action},
                after_data={
                    "_undo_of": audit.pk,
                    "direction": direction,
                    "summary": summary,
                },
            )

        return RestoreResult(
            direction=direction,
            audit_id=audit.pk,
            audit_action=audit.action,
            entity_type=entity_type,
            entity_id=audit.entity_id,
            new_audit_id=new_audit.pk,
            summary=summary,
        )

    @staticmethod
    def _guard_no_newer_changes(audit: AuditLog, entity_type: str) -> None:
        """Refuse if a newer *user* change targets the same entity."""
        if audit.entity_id is None:
            return
        newer = (
            AuditLog.objects.filter(
                entity_type=entity_type,
                entity_id=audit.entity_id,
                created_at__gt=audit.created_at,
            )
            .exclude(action__endswith=_UNDONE_SUFFIX)
            .exclude(action__endswith=_REDONE_SUFFIX)
            .exclude(pk=audit.pk)
            .order_by("created_at")
            .first()
        )
        if newer is not None:
            raise RestoreConflictError(
                f"A newer change (audit #{newer.pk}: {newer.action}) targets "
                f"this {entity_type}. Undo that change first.",
            )

    # ------------------------------------------------------------------
    # Per-verb dispatch
    # ------------------------------------------------------------------
    def _dispatch(
        self, audit: AuditLog, entity_type: str, verb: str, direction: str,
    ) -> str:
        model = apps.get_model(_ENTITY_REGISTRY[entity_type])

        if verb == "created":
            # undo  → delete the row that was created
            # redo  → recreate from after_data
            if direction == "undo":
                return _delete_by_pk(model, audit.entity_id)
            return _restore_row(model, audit.entity_id, _raw_of(audit.after_data))

        if verb == "deleted":
            # undo  → recreate from before_data
            # redo  → delete it again
            if direction == "undo":
                return _restore_row(model, audit.entity_id, _raw_of(audit.before_data))
            return _delete_by_pk(model, audit.entity_id)

        if verb in {"updated", "enabled", "disabled"}:
            target = audit.before_data if direction == "undo" else audit.after_data
            return _patch_row(model, audit.entity_id, _raw_of(target))

        raise NotReversibleError(f"Unhandled verb '{verb}'.")


# ---------------------------------------------------------------------------
# Mutators (each returns a human-readable summary line)
# ---------------------------------------------------------------------------
def _describe_protected(exc) -> str:
    """Return a short human-readable list of objects blocking a delete."""
    objs = getattr(exc, "protected_objects", None) or getattr(exc, "restricted_objects", None)
    if not objs:
        return "related rows"
    counts: dict[str, int] = {}
    for obj in objs:
        name = obj.__class__.__name__
        counts[name] = counts.get(name, 0) + 1
    return ", ".join(f"{n}×{c}" for n, c in counts.items())


def _raw_of(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {}
    raw = data.get("_raw")
    if isinstance(raw, dict):
        return raw
    # Fallback: legacy logs without _raw — try the top-level scalars.
    return {k: v for k, v in data.items() if not isinstance(v, (dict, list))}


def _delete_by_pk(model, pk) -> str:
    if pk is None:
        raise RestoreError("Cannot delete without an entity_id.")
    obj = model.objects.filter(pk=pk).first()
    if obj is None:
        return f"{model.__name__} #{pk} already absent."
    obj.delete()
    return f"Deleted {model.__name__} #{pk}."


def _restore_row(model, pk, raw: dict[str, Any]) -> str:
    if pk is None:
        raise RestoreError("Cannot restore without an entity_id.")
    if model.objects.filter(pk=pk).exists():
        return f"{model.__name__} #{pk} already present."
    kwargs = _normalise_payload(model, raw)
    _ensure_required_fields(model, kwargs)
    obj = model(pk=pk, **kwargs)
    obj.save(force_insert=True)
    return f"Recreated {model.__name__} #{pk}."


def _patch_row(model, pk, raw: dict[str, Any]) -> str:
    if pk is None:
        raise RestoreError("Cannot patch without an entity_id.")
    obj = model.objects.filter(pk=pk).first()
    if obj is None:
        raise RestoreConflictError(
            f"{model.__name__} #{pk} no longer exists.",
        )
    target = _normalise_payload(model, raw)
    changed: list[str] = []
    for attname, value in target.items():
        current = getattr(obj, attname, None)
        if current != value:
            setattr(obj, attname, value)
            changed.append(attname)
    if not changed:
        return f"{model.__name__} #{pk} already at target state."
    obj.save(update_fields=changed + _maybe_updated_at(model))
    return f"Patched {model.__name__} #{pk}: {', '.join(changed)}."


# ---------------------------------------------------------------------------
# Payload normalisation — bridges legacy serializer-shape audit rows and the
# concrete column attnames the model actually expects.
# ---------------------------------------------------------------------------
def _normalise_payload(model, raw: dict[str, Any]) -> dict[str, Any]:
    """Translate audit payload keys/values into ``{attname: python_value}``.

    Handles three sources of mismatch between snapshots and the model:

    * **FK keys** stored as ``branch`` (serializer name) instead of
      ``branch_id`` (attname).
    * **FK values** that are nested dicts (``{"id": 5, ...}``) rather than
      bare ids.
    * **Scalar values** stored as ISO strings / decimals from JSONField,
      converted back to the right Python type for the field.

    Unknown keys, primary key, and non-editable fields are silently dropped.
    """
    if not raw:
        return {}

    by_attname = {f.attname: f for f in model._meta.concrete_fields}
    by_name = {f.name: f for f in model._meta.concrete_fields}

    out: dict[str, Any] = {}
    for key, value in raw.items():
        if key.startswith("_") or key in {"id", "pk"}:
            continue
        field = by_attname.get(key) or by_name.get(key)
        if field is None or not field.editable or field.primary_key:
            continue
        attname = field.attname

        # FK serializer-style: unwrap {"id": N} → N
        if field.is_relation and isinstance(value, dict):
            value = value.get("id") or value.get("pk")
        # FK with no value isn't useful — and would NULL a NOT NULL column
        if field.is_relation and value in (None, ""):
            # Only skip if NOT NULL; otherwise allow it through to clear the FK.
            if not field.null:
                continue

        try:
            value = _coerce_value(field, value)
        except Exception:  # pragma: no cover — keep restore best-effort
            continue
        out[attname] = value
    return out


def _coerce_value(field, value):
    """Best-effort cast a JSON-stored value back to the field's Python type."""
    if value is None:
        return None
    # Decimal / numbers come back as strings from JSONField
    internal = field.get_internal_type()
    if internal == "DecimalField" and not isinstance(value, _decimal.Decimal):
        return _decimal.Decimal(str(value))
    if internal in {"DateTimeField"} and isinstance(value, str):
        from django.utils.dateparse import parse_datetime

        parsed = parse_datetime(value)
        return parsed if parsed is not None else value
    if internal == "DateField" and isinstance(value, str):
        from django.utils.dateparse import parse_date

        parsed = parse_date(value)
        return parsed if parsed is not None else value
    if internal == "TimeField" and isinstance(value, str):
        from django.utils.dateparse import parse_time

        parsed = parse_time(value)
        return parsed if parsed is not None else value
    if internal == "UUIDField" and isinstance(value, str):
        import uuid as _uuid

        try:
            return _uuid.UUID(value)
        except ValueError:
            return value
    if internal in {"IntegerField", "BigIntegerField", "PositiveIntegerField",
                    "PositiveSmallIntegerField", "SmallIntegerField",
                    "AutoField", "BigAutoField"}:
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if internal == "BooleanField":
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes", "on"}
        return bool(value)
    return value


def _ensure_required_fields(model, kwargs: dict[str, Any]) -> None:
    """Raise a friendly error if any NOT NULL editable field is missing."""
    missing = []
    for field in model._meta.concrete_fields:
        if field.primary_key or not field.editable:
            continue
        if field.null or field.has_default() or field.blank:
            continue
        if field.attname not in kwargs:
            missing.append(field.name)
    if missing:
        raise RestoreError(
            f"Cannot recreate {model.__name__}: snapshot is missing required "
            f"fields ({', '.join(missing)}). The original audit row was likely "
            "written before full snapshotting was enabled.",
        )


def _writable_field_map(model) -> dict[str, Any]:
    return {
        f.attname: f
        for f in model._meta.concrete_fields
        if f.editable and not f.primary_key
    }


def _maybe_updated_at(model) -> list[str]:
    return [
        "updated_at"
        for f in model._meta.concrete_fields
        if f.name == "updated_at"
    ][:1]


# ---------------------------------------------------------------------------
# Reverse map: action prefix → entity_type
# ---------------------------------------------------------------------------
_PREFIX_TO_ENTITY: dict[str, str] = {
    "account": "Account",
    "branch": "Branch",
    "room": "Room",
    "room_type": "RoomType",
    "income_rule": "IncomeRule",
    "incomerule": "IncomeRule",
    "systemsettings": "SystemSettings",
    "system_settings": "SystemSettings",
    "penalty": "Penalty",
}
