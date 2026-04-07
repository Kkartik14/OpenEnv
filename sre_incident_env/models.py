from typing import Any, Dict, List, Optional

from openenv.core.env_server import Action, Observation, State


class SREIncidentAction(Action):
    """Action the agent can take in the incident response environment."""

    action_type: str
    target_service: Optional[str] = None
    params: Optional[Dict[str, Any]] = None


class SREIncidentObservation(Observation):
    """Observation returned after each step.

    Inherits from Observation: done (bool), reward (Optional[float]), metadata (dict).
    """

    system_status: Dict[str, Dict[str, Any]] = {}
    active_alerts: List[Dict[str, str]] = []
    action_result: str = ""
    message: str = ""
    step_number: int = 0
    max_steps: int = 25
    available_actions: List[str] = []
    diagnosis_submitted: bool = False
    incident_summary: str = ""


class SREIncidentState(State):
    """Internal state of the environment episode.

    Inherits from State: episode_id (Optional[str]), step_count (int).
    """

    task_name: str = ""
    difficulty: str = ""
    scenario_id: str = ""
    max_steps: int = 25
    diagnosed: bool = False
    remediated: bool = False
