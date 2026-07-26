"""
Scenario Simulator — generates synthetic events to demo the full pipeline
POST /api/simulator/run  → runs the cheating scenario
POST /api/simulator/reset → clears all data
"""

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import time
import threading

from app.core.database import get_db, SessionLocal
from app.models.models import Event, Alert
from app.models.models import Session as SessionModel
from app.core import fusion

router = APIRouter()

_scenario_running = False


def _make_event(session_id, source, event_type, seat_id, x, y,
                protocol=None, rssi=None, duration=None, confidence=None):
    return Event(
        id            = str(uuid.uuid4()),
        session_id    = session_id,
        source_module = source,
        event_type    = event_type,
        seat_id       = seat_id,
        position_x    = x,
        position_y    = y,
        protocol      = protocol,
        rssi_dbm      = rssi,
        duration_s    = duration,
        confidence    = confidence,
    )


def run_scenario_background(session_id: str):
    global _scenario_running
    _scenario_running = True
    db = SessionLocal()

    try:
        steps = [
            # (delay_s, source, event_type, seat_id, x, y, protocol, rssi, duration, confidence)
            (1.0,  "vision",       "person_detected",   "R04-C03", 6.12, 6.4,  None,    None,  None,  0.95),
            (2.0,  "vision",       "person_detected",   "R07-R01", 11.7, 10.0, None,    None,  None,  0.95),
            (3.0,  "rf",           "signal_detected",   "R04-C03", 6.12, 6.4,  "BLE",  -58.0,  5.0,  0.70),
            (4.0,  "vision",       "person_detected",   "R04-C03", 6.12, 6.4,  None,    None,  None,  0.92),
            (5.0,  "localization", "position_estimate", "R04-C03", 6.12, 6.4,  "BLE",  -56.0,  8.0,  0.80),
            (7.0,  "rf",           "signal_detected",   "R04-C03", 6.12, 6.4,  "BLE",  -55.0, 12.0,  0.85),
            (9.0,  "vision",       "person_detected",   "R04-C03", 6.12, 6.4,  None,    None,  None,  0.93),
            (11.0, "rf",           "signal_detected",   "R04-C03", 6.12, 6.4,  "BLE",  -54.0, 18.0,  0.90),
            (13.0, "rf",           "signal_detected",   "R07-R01", 11.7, 10.0, "BLE",  -63.0,  7.0,  0.65),
            (15.0, "vision",       "person_detected",   "R07-R01", 11.7, 10.0, None,    None,  None,  0.88),
            (17.0, "rf",           "signal_detected",   "R07-R01", 11.7, 10.0, "BLE",  -61.0, 12.0,  0.78),
        ]

        for delay, source, etype, seat, x, y, proto, rssi, dur, conf in steps:
            time.sleep(delay)
            ev = _make_event(session_id, source, etype, seat, x, y, proto, rssi, dur, conf)
            db.add(ev)
            db.commit()
            db.refresh(ev)
            fusion.check_and_fuse(db, ev)
            print(f"[SIM] {source:12} | {etype:20} | {seat} | conf={conf}")

        print("[SIM] Scenario complete")
    finally:
        db.close()
        _scenario_running = False


@router.post("/run")
def run_scenario(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    global _scenario_running
    if _scenario_running:
        return {"status": "already running"}

    # Create or reuse active session
    session = db.query(SessionModel).filter(SessionModel.is_active == True).first()
    if not session:
        session = SessionModel(
            id      = str(uuid.uuid4()),
            name    = f"Simulation {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            hall_id = "hall_a",
        )
        db.add(session)
        db.commit()

    background_tasks.add_task(run_scenario_background, session.id)
    return {"status": "started", "session_id": session.id}


@router.post("/reset")
def reset_simulation(db: Session = Depends(get_db)):
    db.query(Alert).delete()
    db.query(Event).delete()
    db.commit()
    return {"status": "reset complete"}


@router.get("/status")
def scenario_status():
    return {"running": _scenario_running}
