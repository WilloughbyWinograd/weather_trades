"""Batched individual-run retrieval with complete local-day reductions."""

import csv, json, time, math
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
from .http import get, ROOT, CACHE, cache_key, ArchiveUnavailable
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
    cfg = settings()
    stations = station_rows()
    rows = []
    # Four model-runs per target day; each coordinate counts toward provider limits.
    count = len(list(days(cfg["study_start"], cfg["study_end"]))) * len(stations) * 4
    if count > 4500:
        raise RuntimeError(
            f"Initial acquisition exceeds 4500 coordinate-run budget: {count}"
        )
    for day in days(cfg["study_start"], cfg["study_end"]):
        for hour in [cfg["previous_cycle_utc_hour"], cfg["current_cycle_utc_hour"]]:
            run = datetime.combine(
                day - timedelta(days=1), datetime.min.time(), UTC
            ) + timedelta(hours=hour)
            for model, identifier in cfg["models"].items():
                params = {
                    "latitude": ",".join(s["latitude"] for s in stations),
                    "longitude": ",".join(s["longitude"] for s in stations),
                    "hourly": "temperature_2m",
                    "models": identifier,
                    "run": run.strftime("%Y-%m-%dT%H:%M"),
                    "forecast_days": 3,
                    "elevation": ",".join("nan" for _ in stations),
                    "cell_selection": "nearest",
                    "timezone": "GMT",
                }
                key = cache_key(cfg["forecast_source"], params)
                cached = (CACHE / (key + ".json")).exists() or (
                    CACHE / (key + ".error")
                ).exists()
                try:
                    data = get(cfg["forecast_source"], params)
                except ArchiveUnavailable:
                    for s in stations:
                        for civil in [False, True]:
                            hours = day_hours(day, s["timezone"], civil)
                            rows.append(
                                {
                                    "city": s["city"],
                                    "cli": s["cli"],
                                    "station": s["icao"],
                                    "date": day.isoformat(),
                                    "model": model,
                                    "run": run.isoformat(),
                                    "run_hour": hour,
                                    "day_basis": "civil" if civil else "standard",
                                    "valid_hours": 0,
                                    "expected_hours": len(hours),
                                    "high_c": "",
                                    "high_f": "",
                                    "status": "source run unavailable",
                                    "requested_latitude": s["latitude"],
                                    "requested_longitude": s["longitude"],
                                    "first_valid": hours[0].isoformat(),
                                    "last_valid": hours[-1].isoformat(),
                                    "source_model": identifier,
                                    "source_cache_key": key,
                                }
                            )
                    write_csv("reports/forecast-samples.csv", rows)
                    print(
                        day,
                        model,
                        hour,
                        "SOURCE RUN UNAVAILABLE",
                        len(rows),
                        flush=True,
                    )
                    if not cached:
                        time.sleep(max(2, len(stations) / 7))
                    continue
                if not isinstance(data, list):
                    data = [data]
                if len(data) != len(stations):
                    raise RuntimeError("Forecast location count mismatch")
                for s, d in zip(stations, data):
                    if (
                        d.get("utc_offset_seconds") != 0
                        or d["hourly_units"]["temperature_2m"] != "°C"
                    ):
                        raise ValueError(
                            "Unexpected forecast timezone or temperature unit"
                        )
                    hourly = d["hourly"]
                    values = {
                        datetime.fromisoformat(t).replace(tzinfo=UTC): v
                        for t, v in zip(hourly["time"], hourly["temperature_2m"])
                    }
                    if len(values) != len(hourly["time"]) or len(hourly["time"]) != len(
                        hourly["temperature_2m"]
                    ):
                        raise ValueError("Duplicate or mismatched forecast time axis")
                    for civil in [False, True]:
                        hours = day_hours(day, s["timezone"], civil)
                        vals = [values.get(t) for t in hours]
                        complete = all(
                            v is not None and math.isfinite(v) for v in vals
                        ) and all(
                            0 <= (t - run).total_seconds() <= 48 * 3600 for t in hours
                        )
                        rows.append(
                            {
                                "city": s["city"],
                                "cli": s["cli"],
                                "station": s["icao"],
                                "date": day.isoformat(),
                                "model": model,
                                "run": run.isoformat(),
                                "run_hour": hour,
                                "day_basis": "civil" if civil else "standard",
                                "valid_hours": sum(v is not None for v in vals),
                                "expected_hours": len(vals),
                                "high_c": max(vals) if complete else "",
                                "high_f": max(vals) * 1.8 + 32 if complete else "",
                                "status": "complete" if complete else "incomplete",
                                "grid_latitude": d["latitude"],
                                "grid_longitude": d["longitude"],
                                "grid_elevation": d.get("elevation"),
                                "requested_latitude": s["latitude"],
                                "requested_longitude": s["longitude"],
                                "first_valid": hours[0].isoformat(),
                                "last_valid": hours[-1].isoformat(),
                                "source_model": identifier,
                            }
                        )
                        rows[-1]["source_cache_key"] = key
                write_csv("reports/forecast-samples.csv", rows)
                print(day, model, hour, len(rows), flush=True)
                # A multi-location request is counted per location; stay below 600/minute.
                if not cached:
                    time.sleep(max(2, len(stations) / 7))
    return rows


if __name__ == "__main__":
    acquire()
