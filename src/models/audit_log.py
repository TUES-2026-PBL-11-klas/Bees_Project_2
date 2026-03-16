import mongoengine as me
from datetime import datetime

class AuditLog(me.Document):
    entity_type = me.StringField(required=True, choices=["route", "vessel", "zone", "event"])
    entity_id = me.ObjectIdField(required=True)
    action = me.StringField(required=True, choices=["created", "updated", "deleted", "recalculated"])
    changed_by = me.StringField()
    details = me.DictField(default=dict)
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "audit_logs",
        "indexes": ["entity_type", "entity_id", "created_at"]
    }
