"""Exhaust location-variable products so a single example cannot hide a city."""

import json
from .http import ROOT, pages

MULTI = [
    "KXRAIN",
    "KXRAINHOLIDAY",
    "KXRAINWKND",
    "KXRAIND",
    "KXSNOWS",
    "KXSNOWSTORM",
    "SNOW",
    "KXHOLIDAYTMAX",
    "KXHOLIDAYTMIN",
    "KXMAXTEMP100",
    "KXCITIESWEATHER",
    "KXECLIPSECOVER",
    "ECLIPSECOVER",
    "KXAQICITY",
    "KXHEATWARNING",
]


def scan():
    out = {}
    for s in MULTI:
        records = {}
        for endpoint in ["/markets", "/historical/markets"]:
            for m in pages(endpoint, "markets", {"series_ticker": s, "limit": 1000}):
                records[m["ticker"]] = {
                    k: m.get(k, "")
                    for k in [
                        "ticker",
                        "title",
                        "rules_primary",
                        "yes_sub_title",
                        "event_ticker",
                    ]
                }
        out[s] = list(records.values())
        (ROOT / "data/raw/multicity-markets.json").write_text(json.dumps(out))
        print(s, len(records), flush=True)
    return out


if __name__ == "__main__":
    scan()
