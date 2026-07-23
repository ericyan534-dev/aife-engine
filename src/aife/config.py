"""Runtime configuration, read from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_MODEL = "gemini-2.0-flash-001"


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    project_id: str
    location: str = "us-central1"
    model_id: str = DEFAULT_MODEL
    max_rpm: int = 300

    @classmethod
    def from_env(cls) -> Settings:
        project_id = os.environ.get("AIFE_PROJECT_ID")
        if not project_id:
            raise ConfigError(
                "AIFE_PROJECT_ID is not set. Point it at the Google Cloud project "
                "that hosts your Vertex AI quota (see .env.example)."
            )
        return cls(
            project_id=project_id,
            location=os.environ.get("AIFE_LOCATION", "us-central1"),
            model_id=os.environ.get("AIFE_MODEL_ID", DEFAULT_MODEL),
            max_rpm=int(os.environ.get("AIFE_MAX_RPM", "300")),
        )
