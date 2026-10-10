"""Original run-file retrieval with complete local-day reductions."""

import csv, json, math
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
from .http import ROOT
from .markets import write_csv

UTC = timezone.utc


def settings():
    return json.loads((ROOT / "config/strategy.json").read_text())


def station_rows():
    return list(csv.DictReader((ROOT / "config/stations.csv").open()))


def days(start, end):
    d = date.fromisoformat(start)
    while d <= date.fromisoformat(end):
        yield d
        d += timedelta(days=1)


def day_hours(day, tz, civil=False):
    zone = ZoneInfo(tz)
    if not civil:
        zone = timezone(datetime(day.year, 1, 15, tzinfo=zone).utcoffset())
    start = datetime.combine(day, datetime.min.time(), zone).astimezone(UTC)
    end = datetime.combine(
        day + timedelta(days=1), datetime.min.time(), zone
    ).astimezone(UTC)
    return [
        start + timedelta(hours=i)
        for i in range(int((end - start).total_seconds() / 3600))
    ]


def acquire():
    """Use the publicly archived files and their completed-run markers directly."""
    from . import archive

    cfg = settings()
    stations = station_rows()
    runs = sorted(
        {
            (
                model,
                (
                    datetime.combine(day - timedelta(days=1), datetime.min.time(), UTC)
                    + timedelta(hours=hour)
                ).isoformat(),
            )
            for day in days(cfg["study_start"], cfg["study_end"])
            for hour in [cfg["previous_cycle_utc_hour"], cfg["current_cycle_utc_hour"]]
            for model in cfg["models"]
        }
    )
    if len(runs) * len(stations) > 4500:
        raise ValueError("Study exceeds the bounded station-run acquisition limit")
    records = archive.acquire(runs, stations)
    result = []
    for record in records:
        run = datetime.fromisoformat(record["run"])
        day = run.date() + timedelta(days=1)
        source = archive.points(record) if record["status"] == "complete" else None
        axis = (
            [datetime.fromisoformat(t) for t in source["valid_times"]] if source else []
        )
        pointmap = {p["cli"]: p for p in source["points"]} if source else {}
        for station in stations:
            point = pointmap.get(station["cli"])
            values = dict(zip(axis, point["values_c"])) if point else {}
            for civil in [False, True]:
                hours = day_hours(day, station["timezone"], civil)
                vals = [values.get(t) for t in hours]
                complete = source is not None and all(
                    v is not None and math.isfinite(v) for v in vals
                )
                row = {
                    "city": station["city"],
                    "cli": station["cli"],
                    "station": station["icao"],
                    "date": day.isoformat(),
                    "model": record["model"],
                    "run": record["run"],
                    "run_hour": run.hour,
                    "day_basis": "civil" if civil else "standard",
                    "valid_hours": sum(v is not None for v in vals),
                    "expected_hours": len(hours),
                    "high_c": max(vals) if complete else "",
                    "high_f": max(vals) * 1.8 + 32 if complete else "",
                    "status": "complete"
                    if complete
                    else record["status"]
                    if not source
                    else "incomplete",
                    "requested_latitude": station["latitude"],
                    "requested_longitude": station["longitude"],
                    "first_valid": hours[0].isoformat(),
                    "last_valid": hours[-1].isoformat(),
                    "source_model": archive.MODELS[record["model"]],
                    "source_cache_key": record["cache_key"],
                    "available_at": record.get("available_at", ""),
                    "availability_evidence": "public run-file completion marker"
                    if complete
                    else "unavailable",
                }
                if point:
                    row.update(
                        grid_latitude=point["latitude"],
                        grid_longitude=point["longitude"],
                        grid_x=point["x"],
                        grid_y=point["y"],
                        source_url=record["data_object"]["url"],
                        source_etag=record["data_object"]["etag"],
                        source_last_modified=record["data_object"]["last_modified"],
                        completion_url=record["completion_object"]["url"],
                        completion_etag=record["completion_object"]["etag"],
                    )
                result.append(row)
    write_csv("reports/forecast-samples.csv", result)
    return result


if __name__ == "__main__":
    acquire()
