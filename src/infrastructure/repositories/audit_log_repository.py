import mongoengine as me
from datetime import datetime


class AuditLog(me.Document):
    event_type = me.StringField(required=True)
    data = me.DictField(required=True)
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "audit_logs",
        "indexes": [
            "event_type",
            "created_at"
        ]
    }
class AuditLogRepository:

    def create_log(self, event_type: str, data: dict):
        log = AuditLog(
            event_type=event_type,
            data=data
        )
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
