"""Audit forecast reductions against preserved original run-file bytes."""

import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from . import archive
from .http import ROOT


def audit(forecasts, stations, check):
    records = json.loads((ROOT / "reports/archive-runs.json").read_text())
    sources = {r["cache_key"]: r for r in records}
    expected = {(r["model"], r["run"]) for r in forecasts}
    check(
        "Every requested run has one source publication record",
        len(records) == len(expected)
        and {(r["model"], r["run"]) for r in records} == expected,
    )
    decoded = {}
    for record in records:
        if record["status"] != "complete":
            continue
        directory = archive.CACHE / record["cache_key"] / record["version_directory"]
        marker = (directory / "meta.json").read_bytes()
        check(
            "Completion marker bytes and identity preserved",
            archive.sha(marker) == record["metadata_sha256"]
            and json.loads(marker) == record["metadata"]
            and hashlib.md5(marker).hexdigest()
            == record["completion_object"]["etag"].strip('"'),
        )
        check(
            "Every source byte range matches its recorded checksum",
            all(
                archive.sha((directory / "ranges" / name).read_bytes()) == value
                for name, value in record["range_sha256"].items()
            ),
        )
        available = archive.publication_time(record)
        check(
            "Forecast availability follows complete original run upload",
            available == archive.stamp(record["available_at"]),
        )
        # Re-decode the original binary ranges with network access prohibited.
        data, receipts, transferred = archive.decode(record, directory, stations, False)
        check(
            "All saved point values re-decode exactly from original source bytes",
            transferred == 0
            and receipts == record["range_sha256"]
            and archive.sha(json.dumps(data, separators=(",", ":")).encode())
            == record["extracted_points_sha256"],
        )
        decoded[record["cache_key"]] = (data, {p["cli"]: p for p in data["points"]})
    bystation = {r["cli"]: r for r in stations}
    distances = defaultdict(float)
    for row in forecasts:
        record = sources[row["source_cache_key"]]
        check(
            "Original source path identifies exact model and initialization",
            record["model"] == row["model"] and record["run"] == row["run"],
        )
        if record["status"] != "complete":
            check(
                "Missing source produces no forecast or availability claim",
                row["status"] != "complete"
                and not row["high_c"]
                and not row["high_f"]
                and not row["available_at"],
            )
            continue
        data, pointmap = decoded[row["source_cache_key"]]
        point = pointmap[row["cli"]]
        station = bystation[row["cli"]]
        check(
            "Station coordinates agree with sourced station table",
            float(row["requested_latitude"]) == float(station["latitude"])
            and float(row["requested_longitude"]) == float(station["longitude"])
            and row["station"] == station["icao"],
        )
        day = datetime.fromisoformat(row["date"])
        zone = ZoneInfo(station["timezone"])
        if row["day_basis"] == "standard":
            zone = timezone(datetime(day.year, 1, 15, tzinfo=zone).utcoffset())
        start = day.replace(tzinfo=zone).astimezone(timezone.utc)
        end = (day + timedelta(days=1)).replace(tzinfo=zone).astimezone(timezone.utc)
        selected = [
            (datetime.fromisoformat(t), v)
            for t, v in zip(data["valid_times"], point["values_c"])
            if start <= datetime.fromisoformat(t) < end
        ]
        check(
            "Forecast day independently aligned to settlement-station local day",
            row["first_valid"] == start.isoformat()
            and row["last_valid"] == (end - timedelta(hours=1)).isoformat(),
        )
        check(
            "Forecast values all belong to the requested future lead window",
            all(
                0
                < (t - datetime.fromisoformat(row["run"])).total_seconds()
                <= 48 * 3600
                for t, _ in selected
            ),
        )
        check(
            "Forecast maximum independently reduced from original stored hours",
            len(selected) == int(row["valid_hours"]) == int(row["expected_hours"]) == 24
            and all(math.isfinite(v) for _, v in selected)
            and max(v for _, v in selected) == float(row["high_c"])
            and abs(max(v for _, v in selected) * 1.8 + 32 - float(row["high_f"]))
            < 1e-9,
        )
        check(
            "Reduction binds values and availability to the same source objects",
            row["source_etag"] == record["data_object"]["etag"]
            and row["completion_etag"] == record["completion_object"]["etag"]
            and row["available_at"] == record["available_at"]
            and int(row["grid_x"]) == point["x"]
            and int(row["grid_y"]) == point["y"],
        )
        a, b = map(math.radians, [float(row["requested_latitude"]), point["latitude"]])
        dl = math.radians(point["longitude"] - float(row["requested_longitude"]))
        distance = 12742 * math.asin(
            min(
                1,
                math.sqrt(
                    math.sin((b - a) / 2) ** 2
                    + math.cos(a) * math.cos(b) * math.sin(dl / 2) ** 2
                ),
            )
        )
        distances[row["model"]] = max(distances[row["model"]], distance)
    return distances
