"""
SpectreNet Team Server — FastAPI backend for multi-operator collaboration.

Endpoints:
  GET  /                       Web dashboard (HTML)
  GET  /api/sessions           List active sessions
  POST /api/sessions           Register a new session
  DELETE /api/sessions/{id}    Kill a session
  GET  /api/loot               All captured loot
  POST /api/loot               Add a loot entry
  GET  /api/notes              All notes
  POST /api/notes              Add a note
  GET  /api/targets            All scope targets
  POST /api/targets            Add a target
  GET  /api/events             SSE stream of real-time events
  POST /api/events/broadcast   Broadcast a message to all listeners
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="SpectreNet Team Server", version="1.0.0")

# ── Shared state ──────────────────────────────────────────────────────────────

_sessions: dict[int, dict] = {}
_loot:     list[dict]      = []
_notes:    list[dict]      = []
_targets:  list[str]       = []
_events:   list[asyncio.Queue] = []
_next_session_id = 1


def _now() -> str:
    return datetime.now().isoformat()


def _broadcast(event_type: str, data: dict) -> None:
    payload = json.dumps({"type": event_type, "data": data, "t": _now()})
    for q in list(_events):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass


# ── Pydantic models ───────────────────────────────────────────────────────────

class SessionIn(BaseModel):
    host:     str
    platform: str = "unknown"
    user:     str = ""
    pid:      int = 0


class LootIn(BaseModel):
    loot_type: str
    text:      str
    operator:  str = "operator"


class NoteIn(BaseModel):
    text:     str
    operator: str = "operator"


class TargetIn(BaseModel):
    cidr: str


class BroadcastIn(BaseModel):
    message:  str
    operator: str = "operator"


# ── Sessions ──────────────────────────────────────────────────────────────────

@app.get("/api/sessions")
def list_sessions() -> dict:
    return {"sessions": list(_sessions.values())}


@app.post("/api/sessions", status_code=201)
def create_session(body: SessionIn) -> dict:
    global _next_session_id
    sid = _next_session_id
    _next_session_id += 1
    session = {
        "id":       sid,
        "host":     body.host,
        "platform": body.platform,
        "user":     body.user,
        "pid":      body.pid,
        "opened":   _now(),
    }
    _sessions[sid] = session
    _broadcast("session_opened", session)
    return session


@app.delete("/api/sessions/{session_id}")
def kill_session(session_id: int) -> dict:
    if session_id not in _sessions:
        raise HTTPException(404, f"Session {session_id} not found")
    s = _sessions.pop(session_id)
    _broadcast("session_killed", {"id": session_id, "host": s["host"]})
    return {"status": "killed", "id": session_id}


# ── Loot ──────────────────────────────────────────────────────────────────────

@app.get("/api/loot")
def get_loot() -> dict:
    return {"loot": _loot}


@app.post("/api/loot", status_code=201)
def add_loot(body: LootIn) -> dict:
    entry = {
        "type":     body.loot_type,
        "text":     body.text,
        "operator": body.operator,
        "t":        _now(),
    }
    _loot.append(entry)
    _broadcast("loot_added", entry)
    return entry


# ── Notes ─────────────────────────────────────────────────────────────────────

@app.get("/api/notes")
def get_notes() -> dict:
    return {"notes": _notes}


@app.post("/api/notes", status_code=201)
def add_note(body: NoteIn) -> dict:
    entry = {"text": body.text, "operator": body.operator, "t": _now()}
    _notes.append(entry)
    _broadcast("note_added", entry)
    return entry


# ── Targets ───────────────────────────────────────────────────────────────────

@app.get("/api/targets")
def get_targets() -> dict:
    return {"targets": _targets}


@app.post("/api/targets", status_code=201)
def add_target(body: TargetIn) -> dict:
    if body.cidr not in _targets:
        _targets.append(body.cidr)
        _broadcast("target_added", {"cidr": body.cidr})
    return {"targets": _targets}


# ── SSE event stream ──────────────────────────────────────────────────────────

@app.get("/api/events")
async def event_stream() -> StreamingResponse:
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _events.append(queue)

    async def generator() -> AsyncIterator[str]:
        try:
            # Send initial state snapshot
            yield f"data: {json.dumps({'type': 'connected', 'sessions': len(_sessions), 'loot': len(_loot)})}\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield "data: {\"type\":\"ping\"}\n\n"
        finally:
            _events.remove(queue)

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.post("/api/events/broadcast")
def broadcast(body: BroadcastIn) -> dict:
    _broadcast("operator_message", {"message": body.message, "operator": body.operator})
    return {"status": "sent"}


# ── Web dashboard ─────────────────────────────────────────────────────────────

_DASHBOARD_TEMPLATE = Path(__file__).parent / "templates" / "dashboard.html"


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    if _DASHBOARD_TEMPLATE.exists():
        return HTMLResponse(_DASHBOARD_TEMPLATE.read_text())
    return HTMLResponse("<h1>SpectreNet Team Server</h1><p>Dashboard template not found.</p>")


# ── Entrypoint ────────────────────────────────────────────────────────────────

def serve(host: str = "0.0.0.0", port: int = 8888) -> None:
    """Start the team server. Call from CLI or scripts."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    serve()
