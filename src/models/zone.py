import mongoengine as me
from datetime import datetime

class Zone(me.Document):
    name = me.StringField(required=True)
    zone_type = me.StringField(required=True, choices=["eco", "conflict", "temporary", "canal"])
    status = me.StringField(choices=["active", "inactive"], default="active")
    geometry = me.PolygonField(required=True)
    description = me.StringField()
    valid_from = me.DateTimeField()
    valid_until = me.DateTimeField()
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "zones",
        "indexes": [
            "zone_type",
            "status",
            {"fields": ["geometry"], "cls": False}
        ]
    }
