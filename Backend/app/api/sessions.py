"""
Sessions API — manage exam sessions
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime

from app.core.database import get_db
from app.core.schemas import SessionIn, SessionOut
from app.models.models import Session as SessionModel

router = APIRouter()


@router.post("/", response_model=SessionOut)
def create_session(data: SessionIn, db: Session = Depends(get_db)):
    session = SessionModel(
        id      = str(uuid.uuid4()),
        name    = data.name,
        hall_id = data.hall_id or "hall_a",
        notes   = data.notes,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/", response_model=List[SessionOut])
def list_sessions(db: Session = Depends(get_db)):
    return db.query(SessionModel).order_by(SessionModel.started_at.desc()).all()


@router.get("/active", response_model=SessionOut)
def get_active_session(db: Session = Depends(get_db)):
    session = db.query(SessionModel).filter(SessionModel.is_active == True).first()
    if not session:
        raise HTTPException(status_code=404, detail="No active session")
    return session


@router.post("/{session_id}/end")
def end_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.is_active = False
    session.ended_at  = datetime.utcnow()
    db.commit()
    return {"status": "ended", "session_id": session_id}
