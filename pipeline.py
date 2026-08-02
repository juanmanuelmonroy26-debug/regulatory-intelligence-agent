from __future__ import annotations

import logging
import sys
import uuid
from datetime import datetime, timezone

from src.audit import AuditLogger
from src.classifier import ImpactClassifier
from src.comparator import Comparator, MAX_DIFFS_BEFORE_SUSPECT
from src.config import Config
from src.interpreter import ClaudeInterpreter
from src.models import InterpretedChange, SourceID
from src.monitor import DIANMonitor, MonitorError
from src.reporter import DocumentReporter
from src.snapshot_manager import SnapshotManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)


def run_source(
    source_id: SourceID,
    monitor: DIANMonitor,
    snap_mgr: SnapshotManager,
    comparator: Comparator,
    classifier: ImpactClassifier,
    interpreter: ClaudeInterpreter,
    audit: AuditLogger,
    config: Config,
) -> tuple[list[InterpretedChange], str | None]:
    """Run the full pipeline for one source. Returns (changes, error_or_None)."""

    # 1 — Fetch
    try:
        fetch = monitor.fetch(source_id)
        audit.log(source_id, "monitor", "ok", f"HTTP {fetch.http_status} — {len(fetch.html)} chars")
    except MonitorError as e:
        audit.log(source_id, "monitor", "error", str(e))
        return [], str(e)

    # 2 — Extract + save snapshot
    try:
        current = snap_mgr.extract(fetch)
        snap_mgr.save(current)
        audit.log(source_id, "snapshot", "ok",
                   f"hash={current.content_hash[:26]} norms={len(current.norms)}")
    except Exception as e:
        audit.log(source_id, "snapshot", "error", str(e))
        return [], str(e)

    # 3 — Load previous snapshot (may be None on first run)
    previous = snap_mgr.load_latest(source_id)

    # 4 — Compare
    comparison = comparator.compare(previous, current)
    suspect = len(comparison.diffs) > MAX_DIFFS_BEFORE_SUSPECT
    audit.log(source_id, "compare", "ok",
               f"hash_changed={comparison.hash_changed} diffs={len(comparison.diffs)} suspect={suspect}")

    if not comparison.hash_changed or not comparison.diffs:
        audit.log(source_id, "pipeline", "skipped", "No changes detected")
        return [], None

    # 5 — Classify
    classified = classifier.classify_all(comparison.diffs)
    audit.log(source_id, "classify", "ok", f"{len(classified)} changes classified")

    # 6 — Interpret
    try:
        interpreted = interpreter.interpret_batch(classified)
        audit.log(source_id, "interpret", "ok", f"{len(interpreted)} changes interpreted")
    except Exception as e:
        audit.log(source_id, "interpret", "error", str(e))
        logger.error(f"Interpretation failed for {source_id}: {e}")
        return [], str(e)

    return interpreted, None


def main() -> None:
    run_id = str(uuid.uuid4())
    config = Config.from_env()

    audit = AuditLogger(run_id=run_id, logs_dir=config.logs_dir)
    monitor = DIANMonitor(timeout=config.monitor_timeout_seconds, max_retries=config.monitor_max_retries)
    snap_mgr = SnapshotManager(snapshots_dir=config.snapshots_dir)
    comparator = Comparator()
    classifier = ImpactClassifier()
    interpreter = ClaudeInterpreter(api_key=config.groq_api_key, model=config.groq_model)
    reporter = DocumentReporter(reports_dir=config.reports_dir)

    is_monday = datetime.now(timezone.utc).weekday() == 0
    sources_to_run: list[SourceID] = [SourceID.MICROSITIOS]
    if is_monday:
        sources_to_run.append(SourceID.NORMOGRAMA)
        logger.info("Monday run — normograma included")

    all_changes: list[InterpretedChange] = []
    error_sources: dict[str, str] = {}
    no_change_sources: list[SourceID] = []

    for source_id in sources_to_run:
        logger.info(f"── Processing {source_id} ──")
        changes, error = run_source(
            source_id, monitor, snap_mgr, comparator,
            classifier, interpreter, audit, config,
        )
        if error:
            error_sources[source_id] = error
        elif not changes:
            no_change_sources.append(source_id)
        else:
            all_changes.extend(changes)

    result = reporter.generate(
        changes=all_changes,
        run_id=run_id,
        sources_monitored=sources_to_run,
        no_changes_sources=no_change_sources,
        error_sources=error_sources,
    )
    audit.log(
        sources_to_run[0], "report", "ok",
        f"Saved: {result.report_path} ({result.changes_included} changes)",
    )
    logger.info(f"Report → {result.report_path}")

    audit.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
