"""
Alerts API — query and manage alerts
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.core.schemas import AlertOut
from app.models.models import Alert
from app.api import ws

router = APIRouter()


@router.get("/", response_model=List[AlertOut])
def list_alerts(
    session_id: Optional[str] = None,
    is_cleared: Optional[bool] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    q = db.query(Alert)
    if session_id is not None: q = q.filter(Alert.session_id == session_id)
    if is_cleared is not None: q = q.filter(Alert.is_cleared == is_cleared)
    return q.order_by(Alert.timestamp_utc.desc()).limit(limit).all()


@router.post("/{alert_id}/clear")
def clear_alert(alert_id: str, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_cleared = True
    alert.cleared_at = datetime.utcnow()
    db.commit()
    return {"status": "cleared", "alert_id": alert_id}


@router.delete("/clear-all")
def clear_all_alerts(db: Session = Depends(get_db)):
    db.query(Alert).update({"is_cleared": True, "cleared_at": datetime.utcnow()})
    db.commit()
    return {"status": "all alerts cleared"}
