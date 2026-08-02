from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel


class Config(BaseModel):
    openai_api_key: str
    snapshots_dir: Path = Path("snapshots")
    logs_dir: Path = Path("logs")
    reports_dir: Path = Path("reports")
    monitor_timeout_seconds: int = 30
    monitor_max_retries: int = 3
    openai_model: str = "gpt-4o"
    max_diffs_before_suspect: int = 50

    @classmethod
    def from_env(cls) -> Config:
        load_dotenv()
        return cls(
            openai_api_key=os.environ["OPENAI_API_KEY"],
            snapshots_dir=Path(os.getenv("SNAPSHOTS_DIR", "snapshots")),
            logs_dir=Path(os.getenv("LOGS_DIR", "logs")),
            reports_dir=Path(os.getenv("REPORTS_DIR", "reports")),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        )
