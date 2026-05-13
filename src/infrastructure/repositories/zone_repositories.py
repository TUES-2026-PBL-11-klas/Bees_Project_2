from typing import Optional

from bson import ObjectId

from src.models.zone import Zone


class ZoneRepository:
    def create(self, zone: Zone) -> Zone:
        zone.save()
        return zone

    def get_by_id(self, zone_id: str) -> Optional[Zone]:
        if not ObjectId.is_valid(zone_id):
            return None
        return Zone.objects(id=ObjectId(zone_id)).first()

    def get_all(self) -> list[Zone]:
        return list(Zone.objects.all())

    def get_active(self) -> list[Zone]:
        return list(Zone.objects(status="active"))

    def get_by_type(self, zone_type: str) -> list[Zone]:
        return list(Zone.objects(zone_type=zone_type))

    def update(self, zone_id: str, data: dict) -> Optional[Zone]:
        zone = self.get_by_id(zone_id)
        if not zone:
            return None
        zone.update(**data)
        zone.reload()
        return zone

    def delete(self, zone_id: str) -> bool:
        zone = self.get_by_id(zone_id)
        if not zone:
            return False
        zone.delete()
        return True

    def activate(self, zone_id: str) -> Optional[Zone]:
        return self.update(zone_id, {"status": "active"})

    def deactivate(self, zone_id: str) -> Optional[Zone]:
        return self.update(zone_id, {"status": "inactive"})
