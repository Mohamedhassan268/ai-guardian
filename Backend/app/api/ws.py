"""
WebSocket — push live events and alerts to the dashboard in real time
Connect: ws://localhost:8000/ws
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
        self.active.remove(ws)
        print(f"[WS] Client disconnected — {len(self.active)} total")

    async def broadcast(self, message: dict):
        data = json.dumps(message)
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)

manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_text(json.dumps({"type": "connected", "message": "Guardian AI live feed"}))
        while True:
            data = await websocket.receive_text()
            # Echo back for ping/pong keepalive
            await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
