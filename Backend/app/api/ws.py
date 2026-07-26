"""
Guardian AI — WebSocket Manager
Pushes live events and alerts to all connected dashboard clients
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import json

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        print(f"[WS] Client connected — {len(self.active)} total")

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
        print(f"[WS] Client disconnected — {len(self.active)} total")

    async def broadcast(self, message: dict):
        """Send a message to all connected dashboard clients."""
        data = json.dumps(message, default=str)
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self.active:
                self.active.remove(ws)

    async def send_event(self, event_data: dict):
        """Broadcast an RF/Vision/Fusion event to dashboard."""
        await self.broadcast({"type": "event", "data": event_data})

    async def send_alert(self, alert_data: dict):
        """Broadcast an alert to dashboard."""
        await self.broadcast({"type": "alert", "data": alert_data})


# Global manager instance — imported by events.py and fusion.py
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": "Guardian AI live feed active"
        }))
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
