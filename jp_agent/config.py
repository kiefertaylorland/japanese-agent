from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "jp-agent"
DEFAULT_DB_FILENAME = "jp_agent.db"
DEFAULT_DATA_DIRNAME = "data"


@dataclass(frozen=True)
class Paths:
    data_dir: Path
    db_path: Path


def resolve_paths(db_path: str | None = None, data_dir: str | None = None) -> Paths:
    env_db = os.getenv("JP_AGENT_DB")
    resolved_db = Path(db_path or env_db or DEFAULT_DB_FILENAME).expanduser().resolve()
    resolved_data = Path(data_dir or DEFAULT_DATA_DIRNAME).expanduser().resolve()
    return Paths(data_dir=resolved_data, db_path=resolved_db)
