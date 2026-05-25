import mongoengine as me
from typing import Optional

class Port(me.Document):
    port_id = me.StringField(required=True, unique=True)
    latitude = me.FloatField(required=True)
    longitude = me.FloatField(required=True)
    name = me.StringField(required=True)
    max_draft_m = me.FloatField(null=True)
    aliases = me.ListField(me.StringField(), default=list)
    is_waypoint = me.BooleanField(default=False)

    meta = {
        "collection": "ports",
        "indexes": [
            "port_id",
            "name",
            "aliases",
            "is_waypoint"
        ]
    }
