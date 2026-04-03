from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class ZoneCreateSchema(BaseModel):
    name: str
    zone_type: str
    status: Optional[str] = "active"
    geometry: Dict[str, Any]
    description: Optional[str] = None

    class Config:
        from_attributes = True


class ZoneUpdateSchema(BaseModel):
    name: Optional[str] = None
    zone_type: Optional[str] = None
    status: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True
