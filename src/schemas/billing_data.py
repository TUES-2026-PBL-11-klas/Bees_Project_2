from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BillingAddressSchema(BaseModel):
    line1: str
    line2: Optional[str] = None
    city: str
    region: Optional[str] = None
    postal_code: Optional[str] = None
    country: str


class UsageRecordSchema(BaseModel):
    period_start: datetime
    period_end: datetime
    route_calculations: int = 0
    ai_reroutes: int = 0
    api_calls: int = 0


class BillingDataCreateSchema(BaseModel):
    company_id: str
    billing_email: str
    billing_address: Optional[BillingAddressSchema] = None
    vat_number: Optional[str] = None
    payment_method: str = "invoice"
    subscription_tier: str = "trial"
    subscription_started_at: Optional[datetime] = None
    subscription_renews_at: Optional[datetime] = None


class BillingDataUpdateSchema(BaseModel):
    billing_email: Optional[str] = None
    billing_address: Optional[BillingAddressSchema] = None
    vat_number: Optional[str] = None
    payment_method: Optional[str] = None
    subscription_tier: Optional[str] = None
    subscription_started_at: Optional[datetime] = None
    subscription_renews_at: Optional[datetime] = None
