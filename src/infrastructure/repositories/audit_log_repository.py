from typing import Any, Optional

from bson import ObjectId

from src.models.audit_log import AuditLog


def _coerce_object_id(value: Any) -> Optional[ObjectId]:
    """Best-effort coercion to ObjectId; returns None for unusable values.

    Accepts a real ObjectId, a 24-hex string, or None. Anything else
    (e.g. a non-ObjectId string from an external event payload) is
    silently dropped so the audit log keeps writing instead of raising
    a ValidationError mid-dispatch.
    """
    if value is None:
        return None
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


class AuditLogRepository:
    def create_log(
        self,
        event_type: str,
        data: dict,
        *,
        entity_type: Optional[str] = None,
        entity_id: Any = None,
        action: Optional[str] = None,
        changed_by: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> AuditLog:
        """Persist a single audit log entry.

        Accepts the full AuditLog field set as optional kwargs so callers
        (e.g. the dispatcher) can record entity references and the actor
        without raising on unknown kwargs. ``entity_id`` is coerced to
        ObjectId or dropped if it cannot be parsed — bad ids never crash
        the dispatcher.
        """
        log = AuditLog(
            event_type=event_type,
            data=data or {},
        )
        if entity_type:
            log.entity_type = entity_type
        coerced = _coerce_object_id(entity_id)
        if coerced is not None:
            log.entity_id = coerced
        if action:
            log.action = action
        if changed_by:
            log.changed_by = changed_by
        if details:
            log.details = details
        log.save()
        return log

    def get_all_logs(self):
        return list(AuditLog.objects.order_by("-created_at"))

    def get_logs_by_type(self, event_type: str):
        return list(
            AuditLog.objects(event_type=event_type).order_by("-created_at")
        )

    def get_last_log(self):
        return AuditLog.objects.order_by("-created_at").first()
