from typing import Optional

from bson import ObjectId

from src.models.billing_data import BillingData, UsageRecord


class BillingDataRepository:
    """CRUD for BillingData, always scoped by company_id (one record per company)."""

    def create(self, data: dict) -> BillingData:
        record = BillingData(**data)
        record.save()
        return record

    def get_for_company(self, company_id: str) -> Optional[BillingData]:
        if not ObjectId.is_valid(company_id):
            return None
        return BillingData.objects(company_id=ObjectId(company_id)).first()

    def update(self, company_id: str, data: dict) -> Optional[BillingData]:
        record = self.get_for_company(company_id)
        if not record:
            return None
        for key, value in data.items():
            setattr(record, key, value)
        record.touch()
        record.save()
        return record

    def delete(self, company_id: str) -> bool:
        record = self.get_for_company(company_id)
        if not record:
            return False
        record.delete()
        return True

    def append_usage(
        self, company_id: str, usage: dict
    ) -> Optional[BillingData]:
        record = self.get_for_company(company_id)
        if not record:
            return None
        record.usage.append(UsageRecord(**usage))
        record.touch()
        record.save()
        return record
