import mongoengine as me
from datetime import datetime

class Waypoint(me.EmbeddedDocument):
    sequence = me.IntField(required=True)
    coordinates = me.ListField(me.FloatField(), required=True)  # [lon, lat]
    point_type = me.StringField(choices=["waypoint", "port", "canal", "checkpoint"])

class Route(me.Document):
    request_id = me.ObjectIdField(required=True)
    company_id = me.ObjectIdField(required=True)
    vessel_id = me.ObjectIdField(required=True)
    optimization_mode = me.StringField(choices=["fastest", "eco"])
    total_distance_nm = me.FloatField()
    estimated_duration_h = me.FloatField()
    estimated_fuel_tons = me.FloatField()
    waypoints = me.EmbeddedDocumentListField(Waypoint, default=list)
    is_valid = me.BooleanField(default=True)
    calculated_at = me.DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "routes",
        "indexes": ["request_id", "company_id", "vessel_id"]
    }
