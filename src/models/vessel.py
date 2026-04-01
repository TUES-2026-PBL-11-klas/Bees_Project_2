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
        "allow_inheritance": True,
        "indexes": ["company_id", "imo_number", "current_status",
                    {"fields": ["current_position"], "cls": False, "sparse": True}]
    }

    def get_capacity_info(self) -> str:
        """Базов метод, който ще бъде презаписан (overridden) от наследниците."""
        raise NotImplementedError("Subclasses must implement this method")


class Tanker(Vessel):
    """Специфичен модел за Танкери."""
    barrels_capacity = me.IntField(default=0)
    is_hazardous = me.BooleanField(default=True)

    def get_capacity_info(self) -> str:
        hazard = "Hazardous" if self.is_hazardous else "Non-hazardous"
        return f"Capacity: {self.barrels_capacity} barrels ({hazard})"


class ContainerShip(Vessel):
    """Специфичен модел за Контейнеровози."""
    teu_capacity = me.IntField(default=0)

    def get_capacity_info(self) -> str:
        return f"Capacity: {self.teu_capacity} TEU"
