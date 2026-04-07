"""FastAPI application for the SRE Incident Response Environment."""

from openenv.core.env_server import create_fastapi_app

from ..models import SREIncidentAction, SREIncidentObservation
from .environment import SREIncidentEnvironment

app = create_fastapi_app(
    SREIncidentEnvironment,
    action_cls=SREIncidentAction,
    observation_cls=SREIncidentObservation,
)
