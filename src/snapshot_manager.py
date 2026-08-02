from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from src.models import NormItem, RawFetch, Snapshot, SourceID

logger = logging.getLogger(__name__)

_NORM_PATTERN = re.compile(
    r"(Resolución Conjunta|Resolución|Decreto|Circular|Concepto|Oficio|Ley)\s+[\dA-Za-z\-]+(?:\s+de\s+\d{4})?",
    re.IGNORECASE,
)


class SnapshotError(Exception):
    pass


class SnapshotManager:
    def __init__(self, snapshots_dir: Path = Path("snapshots")) -> None:
        self.snapshots_dir = snapshots_dir
        self.snapshots_dir.mkdir(exist_ok=True)

    def extract(self, fetch: RawFetch) -> Snapshot:
        try:
            if fetch.source_id == SourceID.MICROSITIOS:
                return self._extract_micrositios(fetch)
            return self._extract_normograma(fetch)
        except Exception as e:
            logger.error(f"Parse failure for {fetch.source_id}: {e}")
            return Snapshot(
                source_id=fetch.source_id,
                url=fetch.url,
                snapshot_date=fetch.fetched_at,
                content_hash="PARSE_FAILURE",
                norms=[],
                raw_text_full="",
            )

    def save(self, snapshot: Snapshot) -> Path:
        source_dir = self.snapshots_dir / snapshot.source_id
        source_dir.mkdir(exist_ok=True)

        date_str = snapshot.snapshot_date.strftime("%Y-%m-%d")
        dated_path = source_dir / f"{date_str}.json"
        latest_path = source_dir / "latest.json"

        data = snapshot.model_dump_json(indent=2)
        dated_path.write_text(data, encoding="utf-8")
        latest_path.write_text(data, encoding="utf-8")

        logger.info(f"Saved snapshot {snapshot.source_id} → {dated_path} ({len(snapshot.norms)} norms)")
        return dated_path

    def load_latest(self, source_id: SourceID) -> Snapshot | None:
        latest_path = self.snapshots_dir / source_id / "latest.json"
        if not latest_path.exists():
            logger.info(f"No previous snapshot for {source_id} — first run baseline")
            return None
        try:
            return Snapshot.model_validate_json(latest_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to load latest snapshot for {source_id}: {e}")
            return None

    # ── Source-specific extractors ─────────────────────────────────────────────

    def _extract_micrositios(self, fetch: RawFetch) -> Snapshot:
        soup = BeautifulSoup(fetch.html, "html.parser")

        content = (
            soup.find("div", class_=re.compile(r"entry-content|page-content|post-content|content-area"))
            or soup.find("main")
            or soup.find("article")
            or soup.body
        )

        norms = self._extract_norms_from_container(content)
        if not norms:
            logger.warning("No norms extracted from micrositios — possible DOM change, check selectors")

        raw_text_full = "\n".join(n.raw_text for n in norms)
        return Snapshot(
            source_id=fetch.source_id,
            url=fetch.url,
            snapshot_date=fetch.fetched_at,
            content_hash=_sha256(raw_text_full),
            norms=norms,
            raw_text_full=raw_text_full,
        )

    def _extract_normograma(self, fetch: RawFetch) -> Snapshot:
        soup = BeautifulSoup(fetch.html, "html.parser")

        target_header: Tag | None = None
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "strong", "b", "span", "p"]):
            text = tag.get_text(strip=True).lower()
            if "facturación" in text or "facturacion" in text:
                if any(w in text for w in ("sistema", "electrónica", "electronica")):
                    target_header = tag
                    break

        items: list[Tag] = []
        if target_header:
            for sibling in target_header.find_next_siblings():
                if sibling.name in ("h1", "h2", "h3", "h4"):
                    break
                items.append(sibling)
        else:
            logger.warning("'Sistema de Facturación' heading not found in normograma — scanning full page")
            items = list(soup.find_all(["li", "p", "tr"]))

        norms = self._extract_norms_from_tags(items)
        if not norms:
            logger.warning("No norms extracted from normograma")

        raw_text_full = "\n".join(n.raw_text for n in norms)
        return Snapshot(
            source_id=fetch.source_id,
            url=fetch.url,
            snapshot_date=fetch.fetched_at,
            content_hash=_sha256(raw_text_full),
            norms=norms,
            raw_text_full=raw_text_full,
        )

    # ── Shared extraction helpers ──────────────────────────────────────────────

    def _extract_norms_from_container(self, container: Tag | None) -> list[NormItem]:
        if container is None:
            return []
        tags = container.find_all(["li", "p", "tr", "div"])
        return self._extract_norms_from_tags(tags)

    @staticmethod
    def _extract_norms_from_tags(tags: list[Tag]) -> list[NormItem]:
        norms: list[NormItem] = []
        seen: set[str] = set()

        for tag in tags:
            text = tag.get_text(separator=" ", strip=True)
            if not text or len(text) < 10:
                continue
            match = _NORM_PATTERN.search(text)
            if not match:
                continue
            norm_id = match.group(0).strip()
            if norm_id in seen:
                continue
            seen.add(norm_id)

            link = tag.find("a", href=True)
            norms.append(NormItem(
                norm_id=norm_id,
                title=text[:200],
                url=link["href"] if link else None,
                raw_text=text,
            ))

        return norms


def _sha256(text: str) -> str:
    normalized = text.strip().replace("\r\n", "\n")
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()
