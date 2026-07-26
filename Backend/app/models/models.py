"""
Database models — Events, Alerts, Sessions
"""

from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id          = Column(String, primary_key=True)
    name        = Column(String, nullable=False)
    hall_id     = Column(String, default="hall_a")
    started_at  = Column(DateTime, server_default=func.now())
    ended_at    = Column(DateTime, nullable=True)
    is_active   = Column(Boolean, default=True)
    total_seats = Column(Integer, default=99)
    notes       = Column(Text, nullable=True)


class Event(Base):
    __tablename__ = "events"

    id            = Column(String, primary_key=True)
    session_id    = Column(String, nullable=True)
    timestamp_utc = Column(DateTime, server_default=func.now())
    source_module = Column(String, nullable=False)   # rf | vision | localization | fusion
    event_type    = Column(String, nullable=False)   # signal_detected | person_detected | position_estimate | alert
    seat_id       = Column(String, nullable=True)
    position_x    = Column(Float, nullable=True)
    position_y    = Column(Float, nullable=True)
    position_z    = Column(Float, nullable=True)
    error_m       = Column(Float, nullable=True)
    protocol      = Column(String, nullable=True)    # BLE | WIFI | UNKNOWN
    freq_hz       = Column(Float, nullable=True)
    rssi_dbm      = Column(Float, nullable=True)
    bandwidth_hz  = Column(Float, nullable=True)
    duration_s    = Column(Float, nullable=True)
    confidence    = Column(Float, nullable=True)
    evidence_ref  = Column(String, nullable=True)
    raw_payload   = Column(JSON, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id            = Column(String, primary_key=True)
    session_id    = Column(String, nullable=True)
    timestamp_utc = Column(DateTime, server_default=func.now())
    seat_id       = Column(String, nullable=False)
    row           = Column(Integer, nullable=True)
    section       = Column(String, nullable=True)
    protocol      = Column(String, nullable=True)
    rssi_dbm      = Column(Float, nullable=True)
    duration_s    = Column(Float, nullable=True)
    confidence    = Column(Float, nullable=False)
    rf_event_id   = Column(String, nullable=True)
    vision_event_id = Column(String, nullable=True)
    is_cleared    = Column(Boolean, default=False)
    cleared_at    = Column(DateTime, nullable=True)
    notes         = Column(Text, nullable=True)
