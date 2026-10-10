"""Complete series inventory and cursor-exhausted daily-high market acquisition."""

import csv, json
from datetime import datetime, timezone, timedelta
from .http import get, pages, BASE, ROOT


def write_csv(path, rows):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def series():
    return json.loads((ROOT / "data/raw/series.json").read_text())["series"]


def weather_series():
    return [
        s
        for s in series()
        if "weather" in s.get("category", "").lower()
        or s["ticker"] in {"HIGHNY0", "KXHIGHNY0"}
    ]


def daily_high(s):
    return (
        s.get("frequency") == "daily"
        and ("high" in s["title"].lower() or "max" in s["title"].lower())
        and s["ticker"] not in {"KXCITIESWEATHER", "KXHIGHUS", "HIGHUS", "KXHIGHNYD"}
    )


def acquire():
    cfg = json.loads((ROOT / "config/strategy.json").read_text())
    start = datetime.fromisoformat(cfg["study_start"]).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(cfg["study_end"]).replace(
        tzinfo=timezone.utc
    ) + timedelta(days=3)
    cutoff = get(BASE + "/historical/cutoff")
    (ROOT / "data/raw/cutoff.json").write_text(json.dumps(cutoff))
    allmarkets = []
    coverage = []
    for s in weather_series():
        if not daily_high(s):
            continue
        records = []
        for endpoint in ["/markets", "/historical/markets"]:
            # Both sources are exhausted; the same date bounds prevent gaps at migration.
            records += list(
                pages(
                    endpoint,
                    "markets",
                    {
                        "series_ticker": s["ticker"],
                        "min_close_ts": int(start.timestamp()),
                        "max_close_ts": int(end.timestamp()),
                        "limit": 1000,
                    },
                )
            )
        found = {m["ticker"]: m for m in records}
        selected = []
        for m in found.values():
            token = m["event_ticker"].split("-")[-1]
            try:
                day = datetime.strptime(token, "%y%b%d").date().isoformat()
            except ValueError:
                continue
            if cfg["study_start"] <= day <= cfg["study_end"] and m.get("result") in (
                "yes",
                "no",
            ):
                m["series_ticker"] = s["ticker"]
                m["target_date"] = day
                selected.append(m)
        allmarkets += selected
        coverage.append(
            {
                "series": s["ticker"],
                "title": s["title"],
                "markets": len(selected),
                "status": "market records retrieved"
                if selected
                else "no settled daily-high markets in study window",
            }
        )
        (ROOT / "data/raw/markets.json").write_text(json.dumps(allmarkets))
        write_csv("reports/market-acquisition.csv", coverage)
        print(s["ticker"], len(selected), flush=True)
    return allmarkets


if __name__ == "__main__":
    acquire()
