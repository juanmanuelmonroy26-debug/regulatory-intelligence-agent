from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.models import ChangeType, ComparisonResult, NormDiff, NormItem, Snapshot, SourceID

logger = logging.getLogger(__name__)

MAX_DIFFS_BEFORE_SUSPECT = 50


class Comparator:
    def compare(self, previous: Snapshot | None, current: Snapshot) -> ComparisonResult:
        base = dict(
            source_id=current.source_id,
            compared_at=datetime.now(timezone.utc),
            current_date=current.snapshot_date,
            current_hash=current.content_hash,
            previous_date=previous.snapshot_date if previous else None,
            previous_hash=previous.content_hash if previous else None,
        )

        if previous is None:
            logger.info(f"First run for {current.source_id} — baseline established, no diffs")
            return ComparisonResult(**base, hash_changed=False, diffs=[])

        if "PARSE_FAILURE" in (current.content_hash, previous.content_hash):
            logger.warning(f"PARSE_FAILURE in {current.source_id} — skipping comparison")
            return ComparisonResult(**base, hash_changed=False, diffs=[])

        if previous.content_hash == current.content_hash:
            logger.info(f"No change detected for {current.source_id} (hash match)")
            return ComparisonResult(**base, hash_changed=False, diffs=[])

        prev_index = _build_index(previous)
        curr_index = _build_index(current)
        prev_ids = set(prev_index)
        curr_ids = set(curr_index)

        diffs: list[NormDiff] = []

        for norm_id in curr_ids - prev_ids:
            diffs.append(NormDiff(change_type=ChangeType.ADDED, norm_id=norm_id, current=curr_index[norm_id]))

        for norm_id in prev_ids - curr_ids:
            diffs.append(NormDiff(change_type=ChangeType.REMOVED, norm_id=norm_id, previous=prev_index[norm_id]))

        for norm_id in prev_ids & curr_ids:
            if prev_index[norm_id].raw_text != curr_index[norm_id].raw_text:
                diffs.append(NormDiff(
                    change_type=ChangeType.MODIFIED,
                    norm_id=norm_id,
                    previous=prev_index[norm_id],
                    current=curr_index[norm_id],
                ))

        if len(diffs) > MAX_DIFFS_BEFORE_SUSPECT:
            logger.warning(
                f"{current.source_id}: {len(diffs)} diffs detected — "
                "possible DOM/structural change rather than real regulatory update"
            )

        logger.info(f"{current.source_id}: {len(diffs)} diffs (added/removed/modified)")
        return ComparisonResult(**base, hash_changed=True, diffs=diffs)


def _build_index(snapshot: Snapshot) -> dict[str, NormItem]:
    index: dict[str, NormItem] = {}
    for norm in snapshot.norms:
        if norm.norm_id in index:
            logger.warning(f"Duplicate norm_id '{norm.norm_id}' in {snapshot.source_id} snapshot")
        index[norm.norm_id] = norm
    return index
