"""FastAPI application for the SRE Incident Response Environment."""

from openenv.core.env_server import create_fastapi_app

from ..models import SREIncidentAction, SREIncidentObservation
from .environment import SREIncidentEnvironment

app = create_fastapi_app(
    SREIncidentEnvironment,
    action_cls=SREIncidentAction,
    observation_cls=SREIncidentObservation,
)


@app.get("/")
def root():
    return {
        "environment": "SRE Incident Response Environment",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "reset": "/reset",
            "step": "/step",
            "state": "/state",
            "schema": "/schema",
            "metadata": "/metadata",
            "docs": "/docs",
        },
    }
