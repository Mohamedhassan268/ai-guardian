"""
Guardian AI — Fusion Engine
Correlates RF and Vision events by seat + time window → confidence score → alert

Core strategy: match by TIMING not just position.
A BLE signal that appears exactly when a hand moves under a desk is strong evidence.
"""

from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
from datetime import datetime, timedelta
import uuid

from app.models.models import Event, Alert

# ── CONFIGURATION ──
TIME_WINDOW_S        = 30.0
MIN_RF_DURATION_S    = 5.0
CONFIDENCE_THRESHOLD = 0.70

W_RF_ONLY    = 0.40
W_VISION_ONLY= 0.30
W_TEMPORAL   = 0.20
W_DURATION   = 0.10


def compute_confidence(rf_event: Event, vision_event: Event) -> float:
    confidence = 0.0
    if rf_event:
        confidence += W_RF_ONLY
        if rf_event.duration_s and rf_event.duration_s >= MIN_RF_DURATION_S:
            confidence += min(rf_event.duration_s / 30.0, 1.0) * W_DURATION
    if vision_event:
        confidence += W_VISION_ONLY
    if rf_event and vision_event:
        if rf_event.timestamp_utc and vision_event.timestamp_utc:
            delta = abs((rf_event.timestamp_utc - vision_event.timestamp_utc).total_seconds())
            if delta <= TIME_WINDOW_S:
                confidence += (1.0 - delta / TIME_WINDOW_S) * W_TEMPORAL
    return round(min(confidence, 1.0), 3)


def _alert_to_dict(alert: Alert) -> dict:
    return {
        "id":            alert.id,
        "session_id":    alert.session_id,
        "timestamp_utc": str(alert.timestamp_utc) if alert.timestamp_utc else None,
        "seat_id":       alert.seat_id,
        "row":           alert.row,
        "section":       alert.section,
        "protocol":      alert.protocol,
        "rssi_dbm":      alert.rssi_dbm,
        "duration_s":    alert.duration_s,
        "confidence":    alert.confidence,
        "is_cleared":    alert.is_cleared,
    }


async def _broadcast_alert(alert: Alert):
    from app.api.ws import manager
    await manager.send_alert(_alert_to_dict(alert))


# Legacy sync version (used by simulator)
def check_and_fuse(db: Session, new_event: Event):
    if not new_event.seat_id:
        return
    seat_id = new_event.seat_id
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=TIME_WINDOW_S)

    recent = db.query(Event).filter(
        Event.seat_id == seat_id,
        Event.timestamp_utc >= window_start,
        Event.id != new_event.id
    ).all()

    rf_event = vision_event = None
    if new_event.source_module == "rf":
        rf_event = new_event
    elif new_event.source_module in ("vision", "localization"):
        vision_event = new_event

    for ev in recent:
        if ev.source_module == "rf" and rf_event is None:
            rf_event = ev
        elif ev.source_module in ("vision", "localization") and vision_event is None:
            vision_event = ev

    if not rf_event:
        return

    confidence = compute_confidence(rf_event, vision_event)

    if confidence >= CONFIDENCE_THRESHOLD:
        existing = db.query(Alert).filter(
            Alert.seat_id == seat_id,
            Alert.is_cleared == False,
            Alert.timestamp_utc >= window_start
        ).first()

        if existing:
            if confidence > existing.confidence:
                existing.confidence = confidence
                db.commit()
            return

        row = section = None
        try:
            row = int(seat_id[1:3])
            section_char = seat_id[4] if len(seat_id) > 4 else None
            section = {"L": "Left", "C": "Center", "R": "Right"}.get(section_char)
        except Exception:
            pass

        alert = Alert(
            id              = str(uuid.uuid4()),
            session_id      = new_event.session_id,
            seat_id         = seat_id,
            row             = row,
            section         = section,
            protocol        = rf_event.protocol,
            rssi_dbm        = rf_event.rssi_dbm,
            duration_s      = rf_event.duration_s,
            confidence      = confidence,
            rf_event_id     = rf_event.id,
            vision_event_id = vision_event.id if vision_event else None,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        print(f"🚨 ALERT: {seat_id} | confidence={confidence:.0%} | protocol={rf_event.protocol}")


# Async version (used by events API with WebSocket broadcast)
async def check_and_fuse_async(db: Session, new_event: Event, background_tasks: BackgroundTasks):
    if not new_event.seat_id:
        return
    seat_id = new_event.seat_id
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=TIME_WINDOW_S)

    recent = db.query(Event).filter(
        Event.seat_id == seat_id,
        Event.timestamp_utc >= window_start,
        Event.id != new_event.id
    ).all()

    rf_event = vision_event = None
    if new_event.source_module == "rf":
        rf_event = new_event
    elif new_event.source_module in ("vision", "localization"):
        vision_event = new_event

    for ev in recent:
        if ev.source_module == "rf" and rf_event is None:
            rf_event = ev
        elif ev.source_module in ("vision", "localization") and vision_event is None:
            vision_event = ev

    if not rf_event:
        return

    confidence = compute_confidence(rf_event, vision_event)

    if confidence >= CONFIDENCE_THRESHOLD:
        existing = db.query(Alert).filter(
            Alert.seat_id == seat_id,
            Alert.is_cleared == False,
            Alert.timestamp_utc >= window_start
        ).first()

        if existing:
            if confidence > existing.confidence:
                existing.confidence = confidence
                db.commit()
            return

        row = section = None
        try:
            row = int(seat_id[1:3])
            section_char = seat_id[4] if len(seat_id) > 4 else None
            section = {"L": "Left", "C": "Center", "R": "Right"}.get(section_char)
        except Exception:
            pass

        alert = Alert(
            id              = str(uuid.uuid4()),
            session_id      = new_event.session_id,
            seat_id         = seat_id,
            row             = row,
            section         = section,
            protocol        = rf_event.protocol,
            rssi_dbm        = rf_event.rssi_dbm,
            duration_s      = rf_event.duration_s,
            confidence      = confidence,
            rf_event_id     = rf_event.id,
            vision_event_id = vision_event.id if vision_event else None,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)

        # Broadcast alert via WebSocket
        background_tasks.add_task(_broadcast_alert, alert)
        print(f"🚨 ALERT: {seat_id} | confidence={confidence:.0%} | protocol={rf_event.protocol}")
