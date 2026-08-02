from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from src.models import AuditEntry, SourceID

logger = logging.getLogger(__name__)


class AuditLogger:
    def __init__(self, run_id: str, logs_dir: Path = Path("logs")) -> None:
        logs_dir.mkdir(exist_ok=True)
        self.run_id = run_id
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.log_path = logs_dir / f"{date_str}_{run_id[:8]}.jsonl"

    def log(
        self,
        source_id: SourceID,
        stage: str,
        status: Literal["ok", "error", "skipped"],
        detail: str,
    ) -> None:
        entry = AuditEntry(
            run_id=self.run_id,
            timestamp=datetime.now(timezone.utc),
            source_id=source_id,
            stage=stage,
            status=status,
            detail=detail,
        )
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
        logger.info(f"[{stage}] {status}: {detail}")

    def close(self) -> None:
        logger.info(f"Run {self.run_id} complete — audit log: {self.log_path}")
