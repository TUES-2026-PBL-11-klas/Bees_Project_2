from typing import List, Optional

from bson import ObjectId

from src.models.fleet_profile import FleetProfile


class FleetProfileRepository:
    """CRUD for FleetProfile, always scoped by company_id for tenant isolation."""

    def create(self, data: dict) -> FleetProfile:
        profile = FleetProfile(**data)
        profile.save()
        return profile

    def get_by_id(self, profile_id: str, company_id: str) -> Optional[FleetProfile]:
        if not ObjectId.is_valid(profile_id) or not ObjectId.is_valid(company_id):
            return None
        return FleetProfile.objects(
            id=profile_id, company_id=ObjectId(company_id)
        ).first()

    def list_for_company(self, company_id: str) -> List[FleetProfile]:
        if not ObjectId.is_valid(company_id):
            return []
        return list(FleetProfile.objects(company_id=ObjectId(company_id)))

    def update(
        self, profile_id: str, company_id: str, data: dict
    ) -> Optional[FleetProfile]:
        profile = self.get_by_id(profile_id, company_id)
        if not profile:
            return None
        for key, value in data.items():
            setattr(profile, key, value)
        profile.touch()
        profile.save()
        return profile

    def delete(self, profile_id: str, company_id: str) -> bool:
        profile = self.get_by_id(profile_id, company_id)
        if not profile:
            return False
        profile.delete()
        return True
