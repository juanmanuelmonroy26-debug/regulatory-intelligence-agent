from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests

from src.models import RawFetch, SourceID

logger = logging.getLogger(__name__)

SOURCES: dict[SourceID, str] = {
    # Sección 1.6 de la compilación tributaria — cargada directamente sin JS
    SourceID.NORMOGRAMA: "https://normograma.dian.gov.co/dian/compilacion/t_1_normativa_tributaria_parte_06.html",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}


class MonitorError(Exception):
    pass


class DIANMonitor:
    def __init__(self, timeout: int = 30, max_retries: int = 3) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)

    def fetch(self, source_id: SourceID) -> RawFetch:
        url = SOURCES[source_id]
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code in (403, 429):
                    raise MonitorError(f"HTTP {response.status_code} blocked by {url}")
                response.raise_for_status()
                if not response.text.strip():
                    raise MonitorError(f"Empty response body from {url}")
                return RawFetch(
                    source_id=source_id,
                    url=url,
                    fetched_at=datetime.now(timezone.utc),
                    html=response.text,
                    http_status=response.status_code,
                )
            except (MonitorError, requests.RequestException) as e:
                last_error = e
                logger.warning(f"Attempt {attempt}/{self.max_retries} failed for {source_id}: {e}")
                if attempt < self.max_retries:
                    time.sleep(5)

        raise MonitorError(f"All {self.max_retries} attempts failed for {source_id}: {last_error}")

    def fetch_all(self, source_ids: list[SourceID]) -> list[RawFetch]:
        return [self.fetch(sid) for sid in source_ids]
