from pydantic import BaseModel
from typing import Optional


class ApiKeySchema(BaseModel):
    key_hash: str
    label: str
    is_active: Optional[bool] = True
    expires_at: Optional[str] = None


class CompanyCreateSchema(BaseModel):
    name: str
    email: str
    status: Optional[str] = "trial"


class CompanyUpdateSchema(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
