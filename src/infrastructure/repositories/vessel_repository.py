from typing import Optional

from bson import ObjectId

from src.models.vessel import Vessel


class VesselRepository:
    def create(self, vessel: Vessel) -> Vessel:
        vessel.save()
        return vessel

    def get_by_id(self, vessel_id: str) -> Optional[Vessel]:
        if not ObjectId.is_valid(vessel_id):
            return None
        return Vessel.objects(id=ObjectId(vessel_id)).first()

    def get_all(self) -> list[Vessel]:
        return list(Vessel.objects.all())

    def get_by_company(self, company_id: str) -> list[Vessel]:
        if not ObjectId.is_valid(company_id):
            return []
        return list(Vessel.objects(company_id=ObjectId(company_id)))

    def get_by_status(self, status: str) -> list[Vessel]:
        return list(Vessel.objects(current_status=status))

    def update(self, vessel_id: str, data: dict) -> Optional[Vessel]:
        vessel = self.get_by_id(vessel_id)
        if not vessel:
            return None

        vessel.update(**data)
        vessel.reload()
        return vessel

    def delete(self, vessel_id: str) -> bool:
        vessel = self.get_by_id(vessel_id)
        if not vessel:
            return False

        vessel.delete()
        return True
