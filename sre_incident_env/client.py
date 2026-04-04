"""
Synchronous HTTP client for the SRE Incident Response Environment.

Works against both local and remote (HF Spaces) deployments.
"""

import requests
from typing import Any, Dict, Optional

from .models import SREIncidentAction, SREIncidentObservation, SREIncidentState


class SREIncidentEnvClient:
    """Simple HTTP client for interacting with the environment server."""

    def __init__(self, base_url: str = "http://localhost:7860"):
        self.base_url = base_url.rstrip("/")
        self.session_id: Optional[str] = None

    def reset(self, **kwargs) -> SREIncidentObservation:
        resp = requests.post(f"{self.base_url}/reset", json=kwargs)
        resp.raise_for_status()
        data = resp.json()
        self.session_id = data.get("session_id")
        return SREIncidentObservation(**data["observation"])

    def step(self, action: SREIncidentAction) -> SREIncidentObservation:
        payload = {
            "session_id": self.session_id,
            "action": action.model_dump(),
        }
        resp = requests.post(f"{self.base_url}/step", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return SREIncidentObservation(**data["observation"])

    def state(self) -> SREIncidentState:
        resp = requests.get(
            f"{self.base_url}/state", params={"session_id": self.session_id}
        )
        resp.raise_for_status()
        return SREIncidentState(**resp.json())

    def health(self) -> Dict[str, Any]:
        resp = requests.get(f"{self.base_url}/health")
        resp.raise_for_status()
        return resp.json()
