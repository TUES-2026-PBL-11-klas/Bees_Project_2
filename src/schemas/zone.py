from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any

class ZoneCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    zone_type: str
    status: Optional[str] = "active"
    geometry: Dict[str, Any]
    description: Optional[str] = None


class ZoneUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = None
    zone_type: Optional[str] = None
    status: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
