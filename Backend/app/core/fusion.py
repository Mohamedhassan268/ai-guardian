"""
Guardian AI — Fusion Engine
Correlates RF and Vision events by seat + time window → confidence score → alert

Core strategy: match by TIMING not just position.
A BLE signal that appears exactly when a hand moves under a desk is strong evidence.
Position alone spans 2-3 seats; timing narrows it to one person.
"""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

from app.models.models import Event, Alert

# ── CONFIGURATION ──
TIME_WINDOW_S      = 30.0   # seconds — RF and Vision events must be within this window
MIN_RF_DURATION_S  = 5.0    # minimum signal duration to consider
CONFIDENCE_THRESHOLD = 0.70  # fire alert above this confidence

# Confidence weights
W_RF_ONLY        = 0.40   # RF signal detected at seat
W_VISION_ONLY    = 0.30   # Vision person detected at seat
W_TEMPORAL       = 0.20   # RF and Vision within time window
W_DURATION       = 0.10   # signal sustained (longer = more confident


def compute_confidence(rf_event: Event, vision_event: Event) -> float:
    """Compute confidence score from RF + Vision event pair."""
    confidence = 0.0

    # RF contribution
    if rf_event:
        confidence += W_RF_ONLY
        # Duration bonus
        if rf_event.duration_s and rf_event.duration_s >= MIN_RF_DURATION_S:
            duration_bonus = min(rf_event.duration_s / 30.0, 1.0) * W_DURATION
            confidence += duration_bonus

    # Vision contribution
    if vision_event:
        confidence += W_VISION_ONLY

    # Temporal correlation bonus
    if rf_event and vision_event:
        if rf_event.timestamp_utc and vision_event.timestamp_utc:
            delta = abs((rf_event.timestamp_utc - vision_event.timestamp_utc).total_seconds())
            if delta <= TIME_WINDOW_S:
                # Closer in time = higher bonus
                temporal_bonus = (1.0 - delta / TIME_WINDOW_S) * W_TEMPORAL
                confidence += temporal_bonus

    return round(min(confidence, 1.0), 3)


def check_and_fuse(db: Session, new_event: Event):
    """
    Called after every new RF or Vision event.
    Looks for a correlated event at the same seat within the time window.
    If confidence >= threshold, fires an alert.
    """
    if not new_event.seat_id:
        return

    seat_id = new_event.seat_id
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=TIME_WINDOW_S)

    # Find recent events at this seat
    recent = db.query(Event).filter(
        Event.seat_id == seat_id,
        Event.timestamp_utc >= window_start,
        Event.id != new_event.id
    ).all()

    rf_event     = None
    vision_event = None

    # Classify the new event
    if new_event.source_module == "rf":
        rf_event = new_event
    elif new_event.source_module in ("vision", "localization"):
        vision_event = new_event

    # Find matching counterpart in recent events
    for ev in recent:
        if ev.source_module == "rf" and rf_event is None:
            rf_event = ev
        elif ev.source_module in ("vision", "localization") and vision_event is None:
            vision_event = ev

    # Need at least RF to fire
    if not rf_event:
        return

    confidence = compute_confidence(rf_event, vision_event)

    if confidence >= CONFIDENCE_THRESHOLD:
        # Check if alert already exists for this seat recently
        existing = db.query(Alert).filter(
            Alert.seat_id    == seat_id,
            Alert.is_cleared == False,
            Alert.timestamp_utc >= window_start
        ).first()

        if existing:
            # Update confidence if higher
            if confidence > existing.confidence:
                existing.confidence = confidence
                db.commit()
            return

        # Parse seat info
        row     = None
        section = None
        if len(seat_id) >= 3:
            try:
                row = int(seat_id[1:3])
                section_char = seat_id[4] if len(seat_id) > 4 else None
                section = {"L": "Left", "C": "Center", "R": "Right"}.get(section_char)
            except Exception:
                pass

        # Fire new alert
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

        print(f"🚨 ALERT fired: {seat_id} | confidence={confidence:.0%} | protocol={rf_event.protocol}")
