from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class EventBase(BaseModel):
    event_type: str
    zone_id: Optional[str] = None
    affected_routes: Optional[List[str]] = None
    payload: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class EventCreateSchema(EventBase):
    event_type: str


class EventUpdateSchema(BaseModel):
    status: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
