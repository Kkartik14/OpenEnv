from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SREIncidentAction(BaseModel):
    """Action the agent can take in the incident response environment."""

    action_type: str
    target_service: Optional[str] = None
    params: Optional[Dict[str, Any]] = None


class SREIncidentObservation(BaseModel):
    """Observation returned after each step."""

    done: bool = False
    reward: Optional[float] = None
    system_status: Dict[str, Dict[str, Any]]
    active_alerts: List[Dict[str, str]]
    action_result: str
    message: str
    step_number: int
    max_steps: int
    available_actions: List[str]
    diagnosis_submitted: bool = False
    incident_summary: str = ""


class SREIncidentState(BaseModel):
    """Internal state of the environment episode."""

    episode_id: Optional[str] = None
    step_count: int = 0
    task_name: str = ""
    difficulty: str = ""
    scenario_id: str = ""
    max_steps: int = 25
    diagnosed: bool = False
    remediated: bool = False
