from typing import Optional

from bson import ObjectId

from src.models.user import User


class UserRepository:
    def create(self, data: dict) -> User:
        user = User(**data)
        user.save()
        return user

    def get_by_id(self, user_id: str) -> Optional[User]:
        if not ObjectId.is_valid(user_id):
            return None
        return User.objects(id=user_id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return User.objects(email=email).first()

    def list_for_company(self, company_id: str) -> list[User]:
        if not ObjectId.is_valid(company_id):
            return []
        return list(User.objects(company_id=ObjectId(company_id)))
