"""Audit public run-object timestamps without equating them to API availability."""

import csv
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

from .http import ROOT
from .forecasts import settings

MODELS = {"GFS": "ncep_gfs013", "HRRR": "ncep_hrrr_conus"}


def audit():
    cfg = settings()
    with (ROOT / "reports/forecast-samples.csv").open() as source:
        runs = sorted({(r["model"], r["run"]) for r in csv.DictReader(source)})

    def probe(pair):
        model, run = pair
        dt = datetime.fromisoformat(run)
        url = f"https://openmeteo.s3.amazonaws.com/data_run/{MODELS[model]}/{dt:%Y/%m/%d/%H%M}Z/temperature_2m.om"
        response = requests.head(url, timeout=25)
        if response.status_code not in {200, 404}:
            response.raise_for_status()
        headers = response.headers
        modified = (
            parsedate_to_datetime(headers["Last-Modified"])
            if headers.get("Last-Modified")
            else None
        )
        entry = dt.replace(hour=cfg["current_cycle_utc_hour"]) + timedelta(
            hours=cfg.get(
                "release_lag_hours", cfg.get("original_release_lag_hours", 5)
            ),
            minutes=cfg["entry_delay_minutes"] + 1,
        )
        return {
            "model": model,
            "run": run,
            "url": url,
            "status": response.status_code,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "last_modified": modified.isoformat() if modified else None,
            "bytes": headers.get("Content-Length"),
            "etag": headers.get("ETag"),
            "baseline_first_entry": entry.isoformat(),
            "object_modified_after_baseline_first_entry": modified > entry
            if modified
            else None,
            "run_to_last_modified_hours": (modified - dt).total_seconds() / 3600
            if modified
            else None,
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        probes = list(pool.map(probe, runs))
    payload = {
        "purpose": "Complete study-run object metadata audit. This is not proof of historical API accessibility, first publication, or exact equality to the saved API values. Later modification does not rule out an earlier object version.",
        "layout_source": "https://github.com/open-meteo/open-data",
        "probes": probes,
    }
    (ROOT / "reports/publication-probes.json").write_text(
        json.dumps(payload, indent=2) + "\n"
    )
    return payload
