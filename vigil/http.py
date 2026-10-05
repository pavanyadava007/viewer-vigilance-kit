"""Polite HTTP client: env proxies (requests default), rate limit and on-disk cache."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

USER_AGENT = "viewer-vigilance-kit/0.1 (+https://github.com/pavanyadava007/viewer-vigilance-kit)"


class CachedClient:
    def __init__(
        self,
        cache_dir: Path | str = "data/raw",
        min_interval_s: float = 1.0,
        ttl_s: float = 20 * 3600,
        offline: bool = False,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.min_interval_s = min_interval_s
        self.ttl_s = ttl_s
        self.offline = offline
        self._last: dict[str, float] = {}
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.n_network = 0
        self.n_cache = 0

    def _key(self, url: str, params: dict | None) -> Path:
        raw = url + "?" + json.dumps(params or {}, sort_keys=True)
        h = hashlib.sha1(raw.encode()).hexdigest()[:16]
        host = urlparse(url).netloc.replace(":", "_")
        return self.cache_dir / host / f"{h}.raw"

    def get_text(self, url: str, params: dict | None = None, ttl_s: float | None = None) -> str:
        path = self._key(url, params)
        ttl = self.ttl_s if ttl_s is None else ttl_s
        if path.exists() and (self.offline or time.time() - path.stat().st_mtime < ttl):
            self.n_cache += 1
            return path.read_text(encoding="utf-8")
        if self.offline:
            raise FileNotFoundError(f"offline and not cached: {url} {params}")
        host = urlparse(url).netloc
        wait = self.min_interval_s - (time.time() - self._last.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        for attempt in range(4):
            resp = self.session.get(url, params=params, timeout=60)
            self._last[host] = time.time()
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(2**attempt * 2)
                continue
            break
        self.n_network += 1
        # openFDA answers 404 with a JSON body for "no matches"; keep that body.
        if resp.status_code not in (200, 404):
            resp.raise_for_status()
        if "charset" not in resp.headers.get("content-type", "").lower():
            resp.encoding = "utf-8"
        text = resp.text
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return text

    def get_json(self, url: str, params: dict | None = None, ttl_s: float | None = None) -> dict:
        return json.loads(self.get_text(url, params, ttl_s))
