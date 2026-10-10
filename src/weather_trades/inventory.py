"""Keep every weather series visible, including retired and non-temperature products."""

import json, re
from .http import get, BASE, ROOT
from .markets import weather_series, write_csv, daily_high


def build():
    # Bootstrap public discovery inputs so a clean checkout can reproduce acquisition.
    raw = ROOT / "data/raw"
    raw.mkdir(parents=True, exist_ok=True)
    inputs = {
        "series.json": (BASE + "/series", {}),
        "twc-primary.json": (
            "https://weather.com/kalshi/api/climate/primary",
            {"date": "2026-10-08"},
        ),
        "twc-international.json": (
            "https://weather.com/kalshi/api/climate/international",
            {"date": "2026-10-08"},
        ),
    }
    for filename, (url, params) in inputs.items():
        if not (raw / filename).exists():
            (raw / filename).write_text(json.dumps(get(url, params)))
    aliases = {
        "NYC": "New York City",
        "New York": "New York City",
        "LA": "Los Angeles",
        "DC": "Washington, DC",
        "Washington DC": "Washington, DC",
        "NOLA": "New Orleans",
        "Minnesota": "Minneapolis",
        "SATX": "San Antonio",
        "SDX": "Louisville",
        "Sao Paulo": "São Paulo",
        "San Francisco": "San Francisco",
        "St. Louis": "St Louis",
        "St Petersburg": "St. Petersburg",
    }
    stationdata = json.loads((ROOT / "data/raw/twc-primary.json").read_text())[
        "results"
    ]
    intl = json.loads((ROOT / "data/raw/twc-international.json").read_text())["results"]
    names = {s["station"]["city"].split(" (")[0] for s in stationdata} | {
        s["city"] for s in intl
    }
    names |= {
        "Jackson",
        "Rapid City",
        "Des Moines",
        "Wilmington",
        "Norfolk",
        "Charleston",
        "Hatteras Island",
        "Savannah",
        "North Myrtle Beach",
        "Orlando",
        "Death Valley",
        "Buffalo",
        "Reykjavik",
        "Salt Lake City",
        "Aspen",
        "Big Sky",
        "Alta",
        "Park City",
        "Whistler",
        "Breckenridge",
        "Vail",
        "Keystone",
        "Killington",
        "Stowe",
    }
    names |= {
        "Erie",
        "Duluth",
        "Concord",
        "Cleveland",
        "Burlington",
        "Bismarck",
        "Albany",
        "Cincinnati",
        "Columbus",
    }
    aliases.update({n: n for n in names})
    aliases["Cincinnati"] = "Cincinnati / Covington"
    multi_path = ROOT / "data/raw/multicity-markets.json"
    multi = json.loads(multi_path.read_text()) if multi_path.exists() else {}
    result = []
    cityrows = {}
    saved = ROOT / "data/raw/series-samples.json"
    samples = json.loads(saved.read_text()) if saved.exists() else {}
    for s in weather_series():
        t = s["ticker"]
        title = s["title"]
        entry = samples.get(t)
        if entry is None:
            entry = get(BASE + "/markets", {"series_ticker": t, "limit": 1})["markets"]
            if not entry:
                entry = get(
                    BASE + "/historical/markets", {"series_ticker": t, "limit": 1}
                )["markets"]
            samples[t] = entry
            saved.write_text(json.dumps(samples))
        evidence = multi.get(t, entry)
        text = " ".join(
            [title]
            + [m.get("title", "") + " " + m.get("rules_primary", "") for m in evidence]
        )
        cities = {
            v
            for a, v in aliases.items()
            if re.search(r"(?<![A-Za-z])" + re.escape(a) + r"(?![A-Za-z])", text, re.I)
        }
        # Rules take precedence over an incorrect legacy series title.
        if t == "KXHIGHTSDF" or t == "KXLOWTSDF":
            cities = {"Louisville"}
        if t in {"EMERGENCYJAC", "KXEMERGENCYJAC"}:
            cities = {"Jackson, Mississippi"}
        if t == "KXJACWSNOWM":
            cities = {"Jackson, Wyoming"}
        if t == "KXJACKSONOPEN":
            cities = {"Jackson Hole Mountain Resort"}
        cls = "daily high" if daily_high(s) else "other weather product"
        if not cities:
            cls = (
                "named facility; outside daily-high strategy"
                if any(w in title.lower() for w in ["opening", "closing"])
                else "non-city environmental product"
                if entry
                else "no available market; location unspecified"
            )
        for c in cities:
            row = cityrows.setdefault(
                c, {"city": c, "series": set(), "product_classes": set()}
            )
            row["series"].add(t)
            row["product_classes"].add(cls)
        result.append(
            {
                "series": t,
                "title": title,
                "frequency": s.get("frequency"),
                "classification": cls,
                "cities": ";".join(sorted(cities)),
                "sample_market": entry[0]["ticker"] if entry else "",
                "source": "series catalog and all location-variable market rules"
                if t in multi
                else "series catalog and actual market rule sample",
                "station_status": "see dated contract mappings"
                if daily_high(s)
                else "outside initial daily-high strategy",
            }
        )
        write_csv("config/market-classification.csv", result)
        write_csv(
            "reports/city-inventory.csv",
            [
                {
                    k: ";".join(sorted(v)) if isinstance(v, set) else v
                    for k, v in row.items()
                }
                for _, row in sorted(cityrows.items())
            ],
        )
        print(t, len(result), flush=True)
    return result


if __name__ == "__main__":
    build()
