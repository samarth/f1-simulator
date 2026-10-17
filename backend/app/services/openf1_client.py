"""Small OpenF1 client with pacing and an in-memory response cache.

Historical data is free and needs no API key. The free tier allows about
3 requests/second and 30 requests/minute, so calls are spaced out and
successful responses are reused.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque

import httpx

from ..config import OPENF1_BASE_URL

logger = logging.getLogger(__name__)

# Stay under the published free-tier limits (3 req/s, 30 req/min).
MIN_INTERVAL_SECONDS = 0.4
MAX_REQUESTS_PER_MINUTE = 25
# Schedule data changes rarely. Lap data for a finished race does not change.
SCHEDULE_TTL_SECONDS = 30 * 60
RACE_TTL_SECONDS = 6 * 60 * 60
EMPTY_TTL_SECONDS = 60
MAX_ATTEMPTS = 4


class OpenF1Error(Exception):
    """A failure talking to OpenF1 that should be shown to the user."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class OpenF1Client:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recent: deque[float] = deque()
        self._cache: dict[tuple, tuple[float, list]] = {}
        self._http = httpx.Client(
            timeout=httpx.Timeout(45.0, connect=10.0),
            headers={"User-Agent": "f1-strategy-simulator", "Accept": "application/json"},
            follow_redirects=True,
        )

    def base_url(self) -> str:
        return os.environ.get("OPENF1_BASE_URL", OPENF1_BASE_URL).rstrip("/")

    def get_json(self, path: str, params: dict | None = None, *, schedule: bool = False) -> list:
        """GET a list endpoint. `schedule` uses a shorter cache (meetings, sessions)."""
        query = tuple(sorted((params or {}).items()))
        key = (self.base_url(), path, query)
        cached = self._read_cache(key)
        if cached is not None:
            return cached

        data = self._fetch(path, dict(query))
        ttl = EMPTY_TTL_SECONDS if len(data) == 0 else (SCHEDULE_TTL_SECONDS if schedule else RACE_TTL_SECONDS)
        self._write_cache(key, data, ttl)
        return data

    def _read_cache(self, key: tuple) -> list | None:
        with self._lock:
            item = self._cache.get(key)
            if item is None:
                return None
            expires_at, data = item
            if expires_at <= time.monotonic():
                del self._cache[key]
                return None
            return data

    def _write_cache(self, key: tuple, data: list, ttl: float) -> None:
        with self._lock:
            self._cache[key] = (time.monotonic() + ttl, data)

    def _pace(self) -> None:
        with self._lock:
            now = time.monotonic()
            while self._recent and now - self._recent[0] >= 60:
                self._recent.popleft()
            wait = 0.0
            if self._recent:
                wait = max(0.0, MIN_INTERVAL_SECONDS - (now - self._recent[-1]))
            if len(self._recent) >= MAX_REQUESTS_PER_MINUTE:
                wait = max(wait, 60.0 - (now - self._recent[0]) + 0.1)
            self._recent.append(now + wait)
        if wait > 0:
            time.sleep(wait)

    def _fetch(self, path: str, params: dict) -> list:
        url = f"{self.base_url()}/{path.lstrip('/')}"
        last_error: OpenF1Error | None = None
        for attempt in range(MAX_ATTEMPTS):
            self._pace()
            try:
                response = self._http.get(url, params=params)
            except httpx.HTTPError as exc:
                logger.warning("OpenF1 request failed (%s %s): %s", path, params, exc)
                last_error = OpenF1Error(
                    "OpenF1 is unreachable. Check your connection and try again.",
                    503,
                )
                time.sleep(1.5 * (attempt + 1))
                continue

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "")
                delay = float(retry_after) if retry_after.isdigit() else min(2 ** attempt, 20)
                logger.warning("OpenF1 rate limited %s; retrying in %.1fs", path, delay)
                last_error = OpenF1Error(
                    "OpenF1 rate limit reached. Wait a minute and try again.",
                    429,
                )
                time.sleep(delay)
                continue

            if response.status_code == 404:
                return []

            if response.status_code >= 500:
                logger.warning("OpenF1 %s returned %s", path, response.status_code)
                last_error = OpenF1Error(
                    "OpenF1 had a problem answering. Try again in a moment.",
                    503,
                )
                time.sleep(1.5 * (attempt + 1))
                continue

            if response.status_code >= 400:
                raise OpenF1Error(
                    f"OpenF1 rejected the request for {path} ({response.status_code}).",
                    502,
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise OpenF1Error("OpenF1 returned a response that was not JSON.", 502) from exc

            if isinstance(payload, dict):
                # Some errors come back as {"detail": "..."} with HTTP 200.
                detail = payload.get("detail") or payload.get("message")
                if detail:
                    raise OpenF1Error(f"OpenF1: {detail}", 502)
                raise OpenF1Error("OpenF1 returned an unexpected response.", 502)
            if not isinstance(payload, list):
                raise OpenF1Error("OpenF1 returned an unexpected response.", 502)
            return payload

        assert last_error is not None
        raise last_error


client = OpenF1Client()
