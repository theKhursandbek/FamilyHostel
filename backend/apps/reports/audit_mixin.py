"""
Audit-trail mixin for DRF ``ModelViewSet`` classes.

Drop :class:`AuditedModelViewSetMixin` into any ``ModelViewSet`` to record
``AuditLog`` rows for every create / update / destroy operation. Snapshots are
captured via the viewset's own serializer so ``before_data`` / ``after_data``
match exactly what the API exposes — which is essential for the undo/redo
restore service that consumes these rows.

Example::

    class BranchViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
        audit_entity_type = "Branch"
        audit_action_prefix = "branch"
        ...

The default ``audit_entity_type`` is the model class name; the default
``audit_action_prefix`` is its lowercase form. Override per viewset when you
want pretty action codes (e.g. ``room_type``) or a stable name decoupled from
the model class.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .services import log_action

if TYPE_CHECKING:  # pragma: no cover
    from rest_framework.viewsets import ModelViewSet

    _Base = ModelViewSet
else:
    _Base = object

__all__ = ["AuditedModelViewSetMixin"]


def _raw_column_values(instance) -> dict[str, Any]:
    """Return JSON-serialisable concrete column values for *instance*.

    Uses each field's ``attname`` so foreign keys are stored as
    ``<name>_id`` integers — exactly the form needed by
    :mod:`apps.reports.restore_service` when re-applying changes.
    Non-primitive types (Decimal, datetime, UUID, files…) are
    serialised as strings so the JSONField storage stays portable.
    """
    import datetime
    import decimal
    import uuid

    out: dict[str, Any] = {}
    for field in instance._meta.concrete_fields:
        if field.primary_key or not field.editable:
            continue
        try:
            value = getattr(instance, field.attname)
        except Exception:  # pragma: no cover
            continue
        if value is None or isinstance(value, (str, int, float, bool)):
            out[field.attname] = value
        elif isinstance(value, decimal.Decimal):
            out[field.attname] = str(value)
        elif isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
            out[field.attname] = value.isoformat()
        elif isinstance(value, uuid.UUID):
            out[field.attname] = str(value)
        else:
            # FieldFile / ImageFieldFile etc. — store the storage name only.
            name = getattr(value, "name", None)
            out[field.attname] = name if isinstance(name, str) else str(value)
    return out


class AuditedModelViewSetMixin(_Base):
    """Mixin that emits ``AuditLog`` rows from ``perform_*`` hooks.

    Configurable class attributes:

    * ``audit_entity_type`` — string stored in ``AuditLog.entity_type``.
        Defaults to ``self.queryset.model.__name__``.
    * ``audit_action_prefix`` — prefix for the dotted action codes
        (``<prefix>.created``, ``<prefix>.updated``, ``<prefix>.deleted``).
        Defaults to ``audit_entity_type.lower()``.
    * ``audit_serializer_class`` — optional serializer used purely for
        snapshotting. Falls back to ``self.get_serializer_class()`` so that
        the audit captures the same shape the API returns.
    """

    audit_entity_type: str | None = None
    audit_action_prefix: str | None = None
    audit_serializer_class = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _audit_entity_type(self) -> str:
        if self.audit_entity_type:
            return self.audit_entity_type
        model = getattr(self, "queryset", None)
        if model is not None and hasattr(model, "model"):
            return model.model.__name__
        return self.__class__.__name__

    def _audit_action_prefix(self) -> str:
        if self.audit_action_prefix:
            return self.audit_action_prefix
        return self._audit_entity_type().lower()

    def _audit_snapshot(self, instance) -> dict[str, Any] | None:
        """Serialize *instance* using the viewset's serializer (read shape).

        Embeds a private ``_raw`` map containing concrete column values
        (using ``attname`` — i.e. ``branch_id`` rather than the related
        object) so :mod:`apps.reports.restore_service` can rebuild or patch
        the row deterministically without round-tripping through nested
        write serializers.
        """
        if instance is None:
            return None
        serializer_class = self.audit_serializer_class or self.get_serializer_class()
        try:
            data = serializer_class(instance, context=self.get_serializer_context()).data
            payload: dict[str, Any] = dict(data) if data is not None else {}
        except Exception:  # pragma: no cover — never let auditing break a write
            payload = {}
        payload["_raw"] = _raw_column_values(instance)
        return payload

    def _audit_log(
        self,
        *,
        verb: str,
        entity_id: int | None,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        prefix = self._audit_action_prefix()
        log_action(
            account=getattr(self.request, "user", None),
            action=f"{prefix}.{verb}",
            entity_type=self._audit_entity_type(),
            entity_id=entity_id,
            before_data=before,
            after_data=after,
        )

    # ------------------------------------------------------------------
    # ModelViewSet hooks
    # ------------------------------------------------------------------
    def perform_create(self, serializer):
        instance = serializer.save()
        self._audit_log(
            verb="created",
            entity_id=getattr(instance, "pk", None),
            before=None,
            after=self._audit_snapshot(instance),
        )

    def perform_update(self, serializer):
        # Snapshot before mutating — re-fetch via serializer to capture
        # current persisted values (pre-save instance).
        before = self._audit_snapshot(serializer.instance)
        instance = serializer.save()
        self._audit_log(
            verb="updated",
            entity_id=getattr(instance, "pk", None),
            before=before,
            after=self._audit_snapshot(instance),
        )

    def perform_destroy(self, instance):
        before = self._audit_snapshot(instance)
        pk = getattr(instance, "pk", None)
        instance.delete()
        self._audit_log(
            verb="deleted",
            entity_id=pk,
            before=before,
            after=None,
        )
