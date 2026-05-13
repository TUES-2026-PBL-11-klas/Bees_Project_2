from typing import Optional

from src.models.company import Company


class CompanyRepository:
    def create(self, company: Company) -> Company:
        company.save()
        return company

    def get_by_id(self, company_id: str) -> Optional[Company]:
        return Company.objects(id=company_id).first()

    def get_all(self) -> list[Company]:
        return list(Company.objects.all())

    def update(self, company_id: str, data: dict) -> Optional[Company]:
        company = self.get_by_id(company_id)
        if not company:
            return None

        company.update(**data)
        company.reload()
        return company

    def delete(self, company_id: str) -> bool:
        company = self.get_by_id(company_id)
        if not company:
            return False

        company.delete()
        return True
