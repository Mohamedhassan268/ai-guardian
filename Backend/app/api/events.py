"""
Events API — receive and query RF/Vision/Fusion events
Broadcasts each event over WebSocket to the dashboard
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.core.database import get_db
from app.core.schemas import EventIn, EventOut
from app.models.models import Event
from app.core import fusion

router = APIRouter()


def _event_to_dict(ev: Event) -> dict:
    return {
        "id":            ev.id,
        "session_id":    ev.session_id,
        "timestamp_utc": str(ev.timestamp_utc) if ev.timestamp_utc else None,
        "source_module": ev.source_module,
        "event_type":    ev.event_type,
        "seat_id":       ev.seat_id,
        "position_x":    ev.position_x,
        "position_y":    ev.position_y,
        "confidence":    ev.confidence,
        "protocol":      ev.protocol,
        "rssi_dbm":      ev.rssi_dbm,
        "duration_s":    ev.duration_s,
    }


async def _broadcast_event(ev: Event):
    """Push event to WebSocket clients after DB commit."""
    from app.api.ws import manager
    await manager.send_event(_event_to_dict(ev))


@router.post("/", response_model=dict)
async def create_event(
    event: EventIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Receive a JSON event from any module (RF, Vision, Fusion)."""
    db_event = Event(
        id            = event.event_id or str(uuid.uuid4()),
        session_id    = event.session_id,
        source_module = event.source_module,
        event_type    = event.event_type,
        seat_id       = event.position.seat    if event.position else None,
        position_x    = event.position.x       if event.position else None,
        position_y    = event.position.y       if event.position else None,
        error_m       = event.position.error_m if event.position else None,
        protocol      = event.signal.protocol  if event.signal   else None,
        freq_hz       = event.signal.freq_hz   if event.signal   else None,
        rssi_dbm      = event.signal.rssi_dbm  if event.signal   else None,
        bandwidth_hz  = event.signal.bandwidth_hz if event.signal else None,
        duration_s    = event.signal.duration_s   if event.signal else None,
        confidence    = event.confidence,
        evidence_ref  = event.evidence_ref,
        raw_payload   = event.model_dump(),
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    # Broadcast to WebSocket clients
    background_tasks.add_task(_broadcast_event, db_event)

    # Run fusion check
    if event.source_module in ("rf", "vision", "localization"):
        await fusion.check_and_fuse_async(db, db_event, background_tasks)

    return {"status": "accepted", "event_id": db_event.id}


@router.get("/", response_model=List[EventOut])
def list_events(
    session_id:    Optional[str] = None,
    source_module: Optional[str] = None,
    seat_id:       Optional[str] = None,
    limit:         int = 100,
    db: Session = Depends(get_db)
):
    q = db.query(Event)
    if session_id:    q = q.filter(Event.session_id    == session_id)
    if source_module: q = q.filter(Event.source_module == source_module)
    if seat_id:       q = q.filter(Event.seat_id       == seat_id)
    return q.order_by(Event.timestamp_utc.desc()).limit(limit).all()


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: str, db: Session = Depends(get_db)):
    ev = db.query(Event).filter(Event.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    return ev
