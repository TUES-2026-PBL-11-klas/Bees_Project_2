import mongoengine as me
from datetime import datetime

class VesselSpecs(me.EmbeddedDocument):
    max_draft_m = me.FloatField()
    max_speed_knots = me.FloatField()
    length_m = me.FloatField()
    beam_m = me.FloatField()

class Vessel(me.Document):
    company_id = me.ObjectIdField(required=True)
    name = me.StringField(required=True)
    imo_number = me.StringField(required=True, unique=True)
    vessel_type = me.StringField(choices=["tanker", "container_ship", "bulk_carrier"])
    specs = me.EmbeddedDocumentField(VesselSpecs)
    fuel_consumption_rate = me.FloatField()
    current_status = me.StringField(choices=["idle", "en_route", "docked"], default="idle")
    current_position = me.PointField()
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "vessels",
        "indexes": ["company_id", "imo_number", "current_status",
                    {"fields": ["current_position"], "cls": False, "sparse": True}]
    }
