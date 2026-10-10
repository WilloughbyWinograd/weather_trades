"""Cross-check dated settlement provider records before admitting city-days."""

import json, re
from .http import get, ROOT
from .stations import TWC
from .markets import write_csv
from .forecasts import days, settings, station_rows


def validate_stations():
    cfg = settings()
    markets = json.loads((ROOT / "data/raw/markets.json").read_text())
    stations = {s["cli"]: s for s in station_rows()}
    rows = []
    for day in days(cfg["study_start"], cfg["study_end"]):
        data = get(TWC, {"date": day.isoformat()})
        lookup = {r["station"]["cliId"]: r for r in data["results"]}
        events = {}
        for m in markets:
            if m["target_date"] == day.isoformat():
                events.setdefault(m["event_ticker"], []).append(m)
        for event, ms in events.items():
            m = ms[0]
            match = re.search(r"\(CLI([A-Z]+)\)", m["rules_primary"])
            cli = match.group(1) if match else ""
            record = lookup.get(cli)
            status = "verified dated provider mapping and settlement value"
            if not record or cli not in stations:
                status = "station unresolved"
            elif "The Weather Company" not in m["rules_primary"]:
                status = "unsupported rule provider"
            elif record["station"]["icao"] != stations[cli]["icao"]:
                status = "station changed"
            elif not record.get("data") or record["data"].get("maxTemp") is None:
                status = "provider value missing"
            elif any(
                float(x["expiration_value"]) != float(record["data"]["maxTemp"])
                for x in ms
            ):
                status = "provider value differs from settled contract"
            rows.append(
                {
                    "event": event,
                    "date": day.isoformat(),
                    "cli": cli,
                    "city": stations.get(cli, {}).get("city", ""),
                    "station": record["station"]["icao"] if record else "",
                    "expiration_value": m.get("expiration_value"),
                    "provider_value": record["data"].get("maxTemp")
                    if record and record.get("data")
                    else "",
                    "status": status,
                    "source": TWC + "?date=" + day.isoformat(),
                }
            )
        write_csv("reports/station-validation.csv", rows)
        print(day, len(rows), flush=True)
    return rows


if __name__ == "__main__":
    validate_stations()
