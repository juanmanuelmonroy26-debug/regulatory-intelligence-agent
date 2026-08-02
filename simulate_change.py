"""
simulate_change.py

Construye un snapshot "anterior" a partir del contenido real de una fuente DIAN,
excluyendo únicamente los norm_ids que tú especificas (basado en evidencia regulatoria real).

Flujo:
  1. Descarga el contenido actual de la fuente oficial.
  2. Extrae los norms y guarda el snapshot actual en {fecha}.json.
  3. Clona ese snapshot y elimina los norm_ids indicados → este es el "anterior".
  4. Guarda el clon como latest.json (el pipeline lo leerá como snapshot previo).

Uso:
  python simulate_change.py --source micrositios --exclude "Resolución 000042 de 2024"
  python simulate_change.py --config simulation_cases/mi_caso.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.config import Config
from src.models import Snapshot, SourceID
from src.monitor import DIANMonitor, MonitorError
from src.snapshot_manager import SnapshotManager, _sha256

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)


def build_previous_snapshot(
    source_id: SourceID,
    exclude_norm_ids: list[str],
    config: Config,
) -> None:
    monitor = DIANMonitor(
        timeout=config.monitor_timeout_seconds,
        max_retries=config.monitor_max_retries,
    )
    snap_mgr = SnapshotManager(snapshots_dir=config.snapshots_dir)

    # 1 — Fetch real content from DIAN
    logger.info(f"Fetching real content from {source_id}...")
    try:
        fetch = monitor.fetch(source_id)
    except MonitorError as e:
        logger.error(f"Fetch failed: {e}")
        sys.exit(1)

    # 2 — Extract and save as the current dated snapshot
    current = snap_mgr.extract(fetch)
    if current.content_hash == "PARSE_FAILURE":
        logger.error("Parse failure — cannot build simulation from broken snapshot")
        sys.exit(1)

    snap_mgr.save(current)
    logger.info(f"Current snapshot saved: {len(current.norms)} norms extracted")

    # 3 — Clone and remove the specified norm_ids
    exclude_set = set(exclude_norm_ids)
    remaining_norms = [n for n in current.norms if n.norm_id not in exclude_set]
    removed = [n.norm_id for n in current.norms if n.norm_id in exclude_set]

    if not removed:
        logger.warning(
            f"None of the specified norm_ids were found in the current snapshot.\n"
            f"Specified: {exclude_norm_ids}\n"
            f"Available: {[n.norm_id for n in current.norms[:10]]}..."
        )
        sys.exit(1)

    logger.info(f"Norms removed from 'previous' snapshot: {removed}")

    raw_text_previous = "\n".join(n.raw_text for n in remaining_norms)
    previous_snapshot = Snapshot(
        source_id=current.source_id,
        url=current.url,
        snapshot_date=current.snapshot_date,
        content_hash=_sha256(raw_text_previous),
        norms=remaining_norms,
        raw_text_full=raw_text_previous,
    )

    # 4 — Save clone as latest.json (the pipeline reads this as "previous")
    latest_path = config.snapshots_dir / source_id / "latest.json"
    latest_path.write_text(previous_snapshot.model_dump_json(indent=2), encoding="utf-8")
    logger.info(
        f"'Previous' snapshot written to {latest_path} "
        f"({len(remaining_norms)} norms, {len(removed)} excluded)"
    )
    logger.info("Ready. Run `python pipeline.py` — the comparator will detect the excluded norms as ADDED.")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Simulate a regulatory change for pipeline testing")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--config",
        help="Path to a JSON config file with source and exclude_norm_ids",
    )
    group.add_argument(
        "--source",
        choices=[s.value for s in SourceID],
        help="Source to fetch (micrositios | normograma | proyectos_normas)",
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        metavar="NORM_ID",
        help="One or more norm_ids to exclude from the previous snapshot",
    )
    args = parser.parse_args()

    if args.config:
        cfg_path = Path(args.config)
        if not cfg_path.exists():
            logger.error(f"Config file not found: {cfg_path}")
            sys.exit(1)
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        source_id = SourceID(data["source"])
        exclude_norm_ids = data["exclude_norm_ids"]
    else:
        if not args.exclude:
            parser.error("--exclude is required when using --source")
        source_id = SourceID(args.source)
        exclude_norm_ids = args.exclude

    config = Config.from_env()
    build_previous_snapshot(source_id, exclude_norm_ids, config)


if __name__ == "__main__":
    main()
