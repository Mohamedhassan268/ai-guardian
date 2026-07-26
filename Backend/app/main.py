"""
Guardian AI — FastAPI Backend
Runs with: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.database import engine, Base
from app.api import events, alerts, sessions, simulator, ws

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Guardian AI",
    description="RF + Vision Intelligence Platform — Exam Security",
    version="1.0.0"
)

# Allow dashboard to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(events.router,    prefix="/api/events",    tags=["Events"])
app.include_router(alerts.router,    prefix="/api/alerts",    tags=["Alerts"])
app.include_router(sessions.router,  prefix="/api/sessions",  tags=["Sessions"])
app.include_router(simulator.router, prefix="/api/simulator", tags=["Simulator"])
app.include_router(ws.router,                                 tags=["WebSocket"])

@app.get("/")
def root():
    return {
        "project": "Guardian AI",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
def health():
    return {"status": "ok"}
