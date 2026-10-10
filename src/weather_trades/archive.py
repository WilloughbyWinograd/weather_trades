"""Read exact archived run objects and retain evidence of their publication.

The source is Open-Meteo's public run-file distribution, not its forecast API.
The run completion marker follows the data upload. Missing or inconsistent
publication evidence is an exclusion, never an inferred release delay.
"""

import hashlib
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import omfiles
import pyproj
import requests

from .http import ROOT

SOURCE_REVISION = "f625df2c2b2d29d7837b1c71660fb226b1864f9b"
GRID_SOURCE = f"https://github.com/open-meteo/open-meteo/blob/{SOURCE_REVISION}/Sources/App/Gfs/GfsDomain.swift"
MODELS = {"GFS": "ncep_gfs013", "HRRR": "ncep_hrrr_conus"}
CACHE = ROOT / "data/raw/point-in-time"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def request(session, method, url, **kwargs):
    for attempt in range(5):
        try:
            response = session.request(method, url, timeout=45, **kwargs)
            if response.status_code in {429, 500, 502, 503, 504}:
                time.sleep(min(15, 2**attempt))
                continue
            return response
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 4:
                raise
            time.sleep(2**attempt)
    raise RuntimeError(f"Source request did not recover: {url}")


def header_record(response):
    h = response.headers
    modified = parsedate_to_datetime(h["Last-Modified"])
    if modified.tzinfo is None:
        raise ValueError("Source timestamp has no timezone")
    return {
        "url": response.url,
        "last_modified": modified.isoformat(),
        "etag": h["ETag"],
        "bytes": int(h["Content-Length"]),
        "version_id": h.get("x-amz-version-id"),
    }


class PinnedRanges:
    """Conditional byte-range reads, with source bytes retained for offline audit."""

    def __init__(self, source, directory, network=True):
        self.source = source
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.network = network
        self.session = requests.Session()
        self.blocks = {}
        self.receipts = {}
        self.transferred = 0

    def size(self, path):
        if path != self.source["url"]:
            raise ValueError("Unexpected source object")
        return self.source["bytes"]

    def cat_file(self, path, start, end):
        size = self.size(path)
        if not 0 <= start < end <= size:
            raise ValueError("Invalid requested byte range")
        blocksize = 65536
        pieces = []
        for offset in range(start // blocksize * blocksize, end, blocksize):
            stop = min(offset + blocksize, size)
            name = f"{offset}-{stop}.bin"
            if offset not in self.blocks:
                file = self.directory / name
                if file.exists():
                    data = file.read_bytes()
                elif not self.network:
                    raise ValueError(f"Missing preserved source range: {file}")
                else:
                    response = request(
                        self.session,
                        "GET",
                        path,
                        headers={
                            "Range": f"bytes={offset}-{stop - 1}",
                            "If-Match": self.source["etag"],
                        },
                    )
                    if (
                        response.status_code != 206
                        or response.headers.get("ETag") != self.source["etag"]
                        or response.headers.get("Content-Range")
                        != f"bytes {offset}-{stop - 1}/{size}"
                        or parsedate_to_datetime(
                            response.headers["Last-Modified"]
                        ).timestamp()
                        != stamp(self.source["last_modified"])
                    ):
                        raise ValueError(
                            "Source version or byte-range response changed"
                        )
                    data = response.content
                    temporary = file.with_suffix(".pending")
                    temporary.write_bytes(data)
                    temporary.replace(file)
                    self.transferred += len(data)
                if len(data) != stop - offset:
                    raise ValueError("Truncated source range")
                self.blocks[offset] = data
                self.receipts[name] = sha(data)
            pieces.append(
                self.blocks[offset][
                    max(0, start - offset) : min(stop - offset, end - offset)
                ]
            )
        return b"".join(pieces)


def gridpoint(model, latitude, longitude):
    """Producer grid specification, pinned above; no elevation correction."""
    if model == "GFS":
        nx, ny = 3072, 1536
        dx, dy = 360 / nx, 0.11714935
        latmin = -dy * (ny - 1) / 2
        x = math.floor((longitude + 180) / dx + 0.5) % nx
        y = math.floor((latitude - latmin) / dy + 0.5)
        lat, lon = latmin + y * dy, -180 + x * dx
    else:
        nx, ny = 1799, 1059
        projection = pyproj.Proj(
            "+proj=lcc +lat_1=38.5 +lat_2=38.5 +lat_0=0 +lon_0=-97.5 +R=6371229 +units=m"
        )
        # Native NOAA GRIB section 3 has more precise coordinates than the
        # rounded Open-Meteo grid bounds. The difference changes Trenton's cell.
        ox, oy = projection(-122.719528, 21.138123)
        dx = dy = 3000.0
        px, py = projection(longitude, latitude)
        x, y = math.floor((px - ox) / dx + 0.5), math.floor((py - oy) / dy + 0.5)
        lon, lat = projection(ox + x * dx, oy + y * dy, inverse=True)
    if not 0 <= x < nx or not 0 <= y < ny:
        raise ValueError("Station outside model grid")
    return {"x": x, "y": y, "latitude": lat, "longitude": lon, "nx": nx, "ny": ny}


def publication_time(record):
    """A completion marker is required; an object modification time alone fails."""
    meta = record["metadata"]
    run = stamp(record["run"])
    data_time = stamp(record["data_object"]["last_modified"])
    marker_time = stamp(record["completion_object"]["last_modified"])
    created = stamp(meta["created_at"])
    if stamp(meta["reference_time"]) != run:
        raise ValueError("Archived run identity differs from requested run")
    if not run <= data_time <= marker_time or not run <= created <= marker_time:
        raise ValueError("Data upload is not covered by the run completion marker")
    if "-" in record["completion_object"]["etag"].strip('"'):
        raise ValueError("Multipart completion marker has ambiguous timestamp")
    if "temperature_2m" not in meta["variables"]:
        raise ValueError("Completion marker does not contain required field")
    return marker_time


def decode(record, directory, stations, network):
    fs = PinnedRanges(record["data_object"], directory / "ranges", network)
    backend = SimpleNamespace(path=record["data_object"]["url"], fs=fs)
    times = record["metadata"]["valid_times"]
    valid = [stamp(t) for t in times]
    if valid != sorted(set(valid)) or valid[0] != stamp(record["run"]):
        raise ValueError("Invalid original-run time axis")
    count = sum(t <= stamp(record["run"]) + 48 * 3600 for t in valid)
    with omfiles.OmFileReader(backend) as reader:
        points = []
        for station in stations:
            point = gridpoint(
                record["model"], float(station["latitude"]), float(station["longitude"])
            )
            if reader.shape != (point["ny"], point["nx"], len(times)):
                raise ValueError(
                    "Archive shape differs from published grid and time axis"
                )
            values = reader[point["y"], point["x"], :count]
            if not np.isfinite(values).all():
                raise ValueError("Missing values in original archived forecast")
            points.append(
                {
                    "station": station["icao"],
                    "cli": station["cli"],
                    **point,
                    "values_c": [float(x) for x in values],
                }
            )
    return {"valid_times": times[:count], "points": points}, fs.receipts, fs.transferred


def acquire_run(model, run, stations):
    dt = datetime.fromisoformat(run)
    prefix = f"https://openmeteo.s3.amazonaws.com/data_run/{MODELS[model]}/{dt:%Y/%m/%d/%H%M}Z"
    key = f"{model}-{dt:%Y%m%dT%H%M}"
    directory = CACHE / key
    directory.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    marker = request(session, "GET", prefix + "/meta.json")
    head = request(session, "HEAD", prefix + "/temperature_2m.om")
    if marker.status_code == 404 or head.status_code == 404:
        record = {
            "model": model,
            "run": run,
            "cache_key": key,
            "status": "source run unavailable",
            "metadata_url": marker.url,
            "metadata_status": marker.status_code,
            "data_url": head.url,
            "data_status": head.status_code,
        }
        (directory / "record.json").write_text(json.dumps(record, indent=2) + "\n")
        return record
    marker.raise_for_status()
    head.raise_for_status()
    record = {
        "model": model,
        "run": run,
        "cache_key": key,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "data_object": header_record(head),
        "completion_object": header_record(marker),
        "metadata": marker.json(),
        "metadata_sha256": sha(marker.content),
        "grid_source": GRID_SOURCE,
    }
    ready = publication_time(record)
    # A rewritten historical object is not eligible for a retrospective trade.
    if ready - stamp(run) >= 12 * 3600:
        raise ValueError(
            "Archive completion too late for the evening strategy; no retrospective substitution"
        )
    identity = sha(
        (record["data_object"]["etag"] + record["completion_object"]["etag"]).encode()
    )[:24]
    directory = directory / identity
    directory.mkdir(parents=True, exist_ok=True)
    record["version_directory"] = identity
    (directory / "meta.json").write_bytes(marker.content)
    points, receipts, transferred = decode(record, directory, stations, True)
    for name, expected in [
        ("meta.json", record["completion_object"]),
        ("temperature_2m.om", record["data_object"]),
    ]:
        after = request(
            session, "HEAD", prefix + "/" + name, headers={"If-Match": expected["etag"]}
        )
        after.raise_for_status()
        if header_record(after) != expected:
            raise ValueError("Source object changed during extraction")
    record.update(
        status="complete",
        available_at=datetime.fromtimestamp(ready, timezone.utc).isoformat(),
        range_sha256=receipts,
        extracted_points_sha256=sha(json.dumps(points, separators=(",", ":")).encode()),
    )
    (directory / "points.json").write_text(
        json.dumps(points, separators=(",", ":")) + "\n"
    )
    (CACHE / key / "record.json").write_text(json.dumps(record, indent=2) + "\n")
    print(
        model,
        run,
        "complete",
        len(receipts),
        "ranges",
        transferred,
        "bytes",
        flush=True,
    )
    return record


def acquire(runs, stations):
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda pair: acquire_run(*pair, stations), runs))
    (ROOT / "reports/archive-runs.json").write_text(
        json.dumps(records, indent=2) + "\n"
    )
    return records


def points(record):
    directory = CACHE / record["cache_key"] / record["version_directory"]
    data = json.loads((directory / "points.json").read_text())
    if (
        sha(json.dumps(data, separators=(",", ":")).encode())
        != record["extracted_points_sha256"]
    ):
        raise ValueError("Saved original-run point values changed")
    return data
