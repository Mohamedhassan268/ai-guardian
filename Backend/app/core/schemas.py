"""
Pydantic schemas — request/response validation
Matches the shared JSON event schema from CLAUDE.md
"""

from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class PositionSchema(BaseModel):
    x:       Optional[float] = None
    y:       Optional[float] = None
    seat:    Optional[str]   = None
    error_m: Optional[float] = None


class SignalSchema(BaseModel):
    protocol:      Optional[str]   = None
    freq_hz:       Optional[float] = None
    bandwidth_hz:  Optional[float] = None
    rssi_dbm:      Optional[float] = None
    duration_s:    Optional[float] = None


class EventIn(BaseModel):
    event_id:      str
    timestamp_utc: Optional[str]  = None
    session_id:    Optional[str]  = None
    source_module: str
    event_type:    str
    position:      Optional[PositionSchema] = None
    signal:        Optional[SignalSchema]   = None
    confidence:    Optional[float]          = None
    evidence_ref:  Optional[str]            = None


class EventOut(BaseModel):
    id:            str
    session_id:    Optional[str]
    timestamp_utc: Optional[datetime]
    source_module: str
    event_type:    str
    seat_id:       Optional[str]
    position_x:    Optional[float]
    position_y:    Optional[float]
    confidence:    Optional[float]
    protocol:      Optional[str]
    rssi_dbm:      Optional[float]
    duration_s:    Optional[float]

    class Config:
        from_attributes = True


class AlertOut(BaseModel):
    id:            str
    session_id:    Optional[str]
    timestamp_utc: Optional[datetime]
    seat_id:       str
    row:           Optional[int]
    section:       Optional[str]
    protocol:      Optional[str]
    rssi_dbm:      Optional[float]
    duration_s:    Optional[float]
    confidence:    float
    is_cleared:    bool

    class Config:
        from_attributes = True


class SessionIn(BaseModel):
    name:       str
    hall_id:    Optional[str] = "hall_a"
    notes:      Optional[str] = None


class SessionOut(BaseModel):
    id:          str
    name:        str
    hall_id:     str
    started_at:  Optional[datetime]
    is_active:   bool
    total_seats: int

    class Config:
        from_attributes = True
