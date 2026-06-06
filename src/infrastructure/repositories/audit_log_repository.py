from src.models.audit_log import AuditLog

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
