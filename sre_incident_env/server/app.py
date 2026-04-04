"""FastAPI application for the SRE Incident Response Environment."""

import json
import uuid
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from ..models import SREIncidentAction, SREIncidentObservation, SREIncidentState
from .environment import SREIncidentEnvironment

sessions: Dict[str, SREIncidentEnvironment] = {}


@asynccontextmanager
async def lifespan(application: FastAPI):
    yield
    sessions.clear()


app = FastAPI(
    title="SRE Incident Response Environment",
    description="OpenEnv environment for training AI agents on SRE incident triage",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/reset")
async def reset(params: dict = None):
    params = params or {}
    env = SREIncidentEnvironment()
    session_id = str(uuid.uuid4())
    sessions[session_id] = env
    obs = env.reset(**params)
    return {"session_id": session_id, "observation": obs.model_dump()}


@app.post("/step")
async def step(payload: dict):
    session_id = payload.get("session_id", "")
    env = sessions.get(session_id)
    if env is None:
        return {"error": "Invalid session_id. Call /reset first."}

    action_data = payload.get("action", {})
    action = SREIncidentAction(**action_data)
    obs = env.step(action)
    result = {"observation": obs.model_dump()}

    if obs.done:
        sessions.pop(session_id, None)

    return result


@app.get("/state")
async def get_state(session_id: str):
    env = sessions.get(session_id)
    if env is None:
        return {"error": "Invalid session_id."}
    return env.state.model_dump()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    env = SREIncidentEnvironment()
    session_id = str(uuid.uuid4())
    sessions[session_id] = env

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type", "")

            if msg_type == "reset":
                params = msg.get("params", {})
                obs = env.reset(**params)
                await ws.send_text(json.dumps({
                    "type": "reset_result",
                    "session_id": session_id,
                    "observation": obs.model_dump(),
                }))

            elif msg_type == "step":
                action_data = msg.get("action", {})
                action = SREIncidentAction(**action_data)
                obs = env.step(action)
                await ws.send_text(json.dumps({
                    "type": "step_result",
                    "observation": obs.model_dump(),
                }))
                if obs.done:
                    break

            elif msg_type == "state":
                await ws.send_text(json.dumps({
                    "type": "state_result",
                    "state": env.state.model_dump(),
                }))

            else:
                await ws.send_text(json.dumps({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                }))

    except WebSocketDisconnect:
        pass
    finally:
        sessions.pop(session_id, None)
