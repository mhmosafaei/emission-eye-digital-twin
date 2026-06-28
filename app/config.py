from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    service_name: str = "emission-eye-digital-co2-twin"
    sprint: int = 3
    database_url: str = "sqlite:///data/emission_eye_twin.sqlite3"


def get_settings() -> Settings:
    database_url = os.getenv("EMISSION_EYE_DB_URL")
    if database_url:
        return Settings(database_url=database_url)

    default_path = Path("data") / "emission_eye_twin.sqlite3"
    return Settings(database_url=f"sqlite:///{default_path.as_posix()}")
