"""Root-level server entry point expected by OpenEnv tooling."""

import uvicorn
from sre_incident_env.server.app import app  # noqa: F401

__all__ = ["app"]


def main():
    uvicorn.run("server.app:app", host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()
