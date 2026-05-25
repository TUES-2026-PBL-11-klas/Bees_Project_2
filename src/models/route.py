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

class RouteHistory(me.Document):
    origin = me.StringField(required=True)
    destination = me.StringField(required=True)
    vessel_type = me.StringField(required=True)
    optimization_mode = me.StringField(choices=["fastest", "eco"], required=True)
    strategy = me.StringField(required=True)
    calculated_time_h = me.FloatField(required=True)
    predicted_fuel_tons = me.FloatField(required=True)
    actual_time_h = me.FloatField(null=True)
    actual_fuel_tons = me.FloatField(null=True)
    calculated_at = me.DateTimeField(default=datetime.utcnow)
    route_id = me.ObjectIdField(null=True)

    meta = {
        "collection": "route_history",
        "indexes": [
            "origin",
            "destination",
            "vessel_type",
            "optimization_mode"
        ]
    }
