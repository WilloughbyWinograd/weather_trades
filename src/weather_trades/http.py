"""Anonymous cached GETs only, with retrieval provenance and response checksums."""

import hashlib, json, time
from pathlib import Path
from urllib.parse import urlencode
import requests

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data/raw/http"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = (
    "weather-trades-research/0.1 (public read-only research)"
)


class ArchiveUnavailable(Exception):
    """An explicit, preserved provider response says this model run is absent."""


def cache_key(url, params=None):
    return hashlib.sha256(
        (url + "?" + urlencode(sorted((params or {}).items()))).encode()
    ).hexdigest()


def get(url, params=None):
    key = cache_key(url, params)
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (key + ".json")
    if path.exists():
        return json.loads(path.read_text())
    if path.with_suffix(".error").exists():
        raise ArchiveUnavailable("Archived model run unavailable: " + key)
    for attempt in range(8):
        time.sleep(0.3)
        try:
            r = SESSION.get(url, params=params, timeout=90)
        except (requests.ConnectionError, requests.Timeout):
            time.sleep(min(60, 2**attempt))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(60, float(r.headers.get("Retry-After", 2**attempt))))
            continue
        r.raise_for_status()
        try:
            data = r.json()
        except requests.exceptions.JSONDecodeError:
            if "modelRunUnavailable" in r.text:
                path.with_suffix(".error").write_bytes(r.content)
                path.with_suffix(".meta").write_text(
                    json.dumps(
                        {
                            "url": r.url,
                            "retrieved_at": time.time(),
                            "sha256": hashlib.sha256(r.content).hexdigest(),
                            "bytes": len(r.content),
                            "error": "model run unavailable",
                            "cache_suffix": ".error",
                        }
                    )
                )
                raise ArchiveUnavailable("Archived model run unavailable: " + key)
            time.sleep(min(60, 2**attempt))
            continue
        temporary = path.with_suffix(".pending")
        temporary.write_bytes(r.content)
        temporary.replace(path)
        (CACHE / (key + ".meta")).write_text(
            json.dumps(
                {
                    "url": r.url,
                    "retrieved_at": time.time(),
                    "sha256": hashlib.sha256(r.content).hexdigest(),
                    "bytes": len(r.content),
                    "cache_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        )
        return data
    raise RuntimeError(f"Source unavailable after retries: {url}")


BASE = "https://external-api.kalshi.com/trade-api/v2"


def pages(endpoint, field, params):
    cursor = ""
    seen = set()
    while True:
        d = get(BASE + endpoint, {**params, **({"cursor": cursor} if cursor else {})})
        yield from d[field]
        cursor = d.get("cursor")
        if not cursor:
            break
        if cursor in seen:
            raise RuntimeError("Repeated pagination cursor")
        seen.add(cursor)
