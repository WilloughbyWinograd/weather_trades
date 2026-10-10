"""Bind each contract's CLI identifier to provider station metadata and NOAA coordinates."""

import json, re
from .http import get, ROOT
from .markets import write_csv

TWC = "https://weather.com/kalshi/api/climate/primary"


def build():
    markets = json.loads((ROOT / "data/raw/markets.json").read_text())
    ids = {
        match.group(1)
        for m in markets
        if (match := re.search(r"\(CLI([A-Z]+)\)", m["rules_primary"]))
    }
    provider = get(TWC, {"date": "2026-10-08"})
    output = []
    for row in provider["results"]:
        s = row["station"]
        if s["cliId"] not in ids:
            continue
        url = "https://api.weather.gov/stations/" + s["icao"]
        d = get(url)
        lon, lat = d["geometry"]["coordinates"][:2]
        output.append(
            {
                "cli": s["cliId"],
                "city": s["city"],
                "icao": s["icao"],
                "timezone": s["timezone"],
                "latitude": lat,
                "longitude": lon,
                "elevation_m": d["properties"]["elevation"]["value"],
                "station_name": d["properties"]["name"],
                "coordinate_source": url,
                "mapping_source": TWC + "?date=2026-10-08",
                "coordinate_epoch": "current metadata; historical relocation not independently audited",
                "status": "provider identifier mapped",
            }
        )
        write_csv("config/stations.csv", output)
        print(s["cliId"], s["icao"], lat, lon, flush=True)
    return output


if __name__ == "__main__":
    build()
