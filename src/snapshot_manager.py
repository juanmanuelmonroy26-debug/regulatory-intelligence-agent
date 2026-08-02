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
            if fetch.source_id == SourceID.NORMOGRAMA:
                return self._extract_normograma(fetch)
            return self._extract_proyectos_normas(fetch)
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

    def _extract_proyectos_normas(self, fetch: RawFetch) -> Snapshot:
        soup = BeautifulSoup(fetch.html, "html.parser")

        # SharePoint page — items are typically in a list view or table
        content = (
            soup.find("div", class_=re.compile(r"ms-listviewtable|ms-WPBody|siteContent|content"))
            or soup.find("table", class_=re.compile(r"ms-listviewtable"))
            or soup.find("main")
            or soup.body
        )

        norms: list[NormItem] = []
        seen: set[str] = set()

        if content:
            for tag in content.find_all(["tr", "li", "div", "p", "a"]):
                text = tag.get_text(separator=" ", strip=True)
                if not text or len(text) < 10:
                    continue

                # For proyectos normas, use the link text as norm_id if no pattern matches
                link = tag.find("a", href=True) if tag.name != "a" else tag
                link_text = link.get_text(strip=True) if link else ""
                href = link["href"] if link and link.has_attr("href") else None

                match = _NORM_PATTERN.search(text)
                norm_id = match.group(0).strip() if match else (link_text[:100] if link_text else text[:100])

                if not norm_id or norm_id in seen:
                    continue
                seen.add(norm_id)

                norms.append(NormItem(
                    norm_id=norm_id,
                    title=text[:200],
                    url=href,
                    raw_text=text,
                ))

        if not norms:
            logger.warning("No items extracted from proyectos_normas — possible DOM change")

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

            matches = list(_NORM_PATTERN.finditer(text))
            if not matches:
                continue

            # Collect all links in this tag indexed by approximate position
            links = tag.find_all("a", href=True)

            for i, match in enumerate(matches):
                norm_id = match.group(0).strip()
                if norm_id in seen:
                    continue
                seen.add(norm_id)

                # Scope raw_text from this match to just past the next norm boundary
                # (+150 so the referenced norm name is included in the description)
                start = match.start()
                end = matches[i + 1].end() + 150 if i + 1 < len(matches) else min(len(text), start + 600)
                raw_text = text[start:end].strip()

                # Pick the closest link to this norm's position in the tag
                url = links[i]["href"] if i < len(links) else (links[0]["href"] if links else None)

                norms.append(NormItem(
                    norm_id=norm_id,
                    title=raw_text[:200],
                    url=url,
                    raw_text=raw_text,
                ))

        return norms


def _sha256(text: str) -> str:
    normalized = text.strip().replace("\r\n", "\n")
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()
