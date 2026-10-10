"""Bounded independent checks against native NOAA two-metre temperature GRIBs."""

import json
from datetime import datetime, timedelta

import requests
import pyproj
import math
import numpy as np

from . import archive
from .forecasts import station_rows, settings
from .http import ROOT

# Load the projection library before ecCodes. The reverse order causes a
# native-library teardown failure with the pinned binary packages.
import eccodes


def run(offline=False):
    cfg = settings()
    records = json.loads((ROOT / "reports/archive-runs.json").read_text())
    first = datetime.fromisoformat(cfg["study_start"]) - timedelta(days=1)
    last = datetime.fromisoformat(cfg["study_end"]) - timedelta(days=1)
    dates = {first.date(), (first + (last - first) / 2).date(), last.date()}
    selected = [
        r
        for r in records
        if datetime.fromisoformat(r["run"]).date() in dates
        and r["status"] == "complete"
    ]
    stations = station_rows()
    output = []
    session = requests.Session()
    directory = ROOT / "data/raw/noaa-validation"
    directory.mkdir(parents=True, exist_ok=True)
    for record in selected:
        dt = datetime.fromisoformat(record["run"])
        model = record["model"]
        lead = 24
        url = (
            f"https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{dt:%Y%m%d}/{dt:%H}/atmos/gfs.t{dt:%H}z.sfluxgrbf{lead:03d}.grib2"
            if model == "GFS"
            else f"https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.{dt:%Y%m%d}/conus/hrrr.t{dt:%H}z.wrfprsf{lead:02d}.grib2"
        )
        key = f"{model}-{dt:%Y%m%dT%H%M}-f{lead}"
        file, receipt_file = directory / (key + ".grib2"), directory / (key + ".json")
        if not file.exists():
            if offline:
                raise ValueError("Missing preserved native NOAA verification source")
            head = archive.request(session, "HEAD", url)
            head.raise_for_status()
            source = archive.header_record(head)
            index = archive.request(session, "GET", url + ".idx")
            index.raise_for_status()
            lines = index.text.splitlines()
            found = [
                i for i, line in enumerate(lines) if ":TMP:2 m above ground:" in line
            ]
            if len(found) != 1:
                raise ValueError("Ambiguous native temperature field")
            i = found[0]
            start = int(lines[i].split(":")[1])
            end = (
                int(lines[i + 1].split(":")[1])
                if i + 1 < len(lines)
                else source["bytes"]
            )
            response = archive.request(
                session,
                "GET",
                url,
                headers={
                    "Range": f"bytes={start}-{end - 1}",
                    "If-Match": source["etag"],
                },
            )
            if (
                response.status_code != 206
                or len(response.content) != end - start
                or response.headers.get("Content-Range")
                != f"bytes {start}-{end - 1}/{source['bytes']}"
                or response.headers.get("ETag") != source["etag"]
            ):
                raise ValueError("Native NOAA source version or byte range changed")
            file.write_bytes(response.content)
            receipt = {
                "source": source,
                "index_line": lines[i],
                "index_sha256": archive.sha(index.content),
                "range_start": start,
                "range_end_exclusive": end,
                "message_sha256": archive.sha(response.content),
            }
            receipt_file.write_text(json.dumps(receipt, indent=2) + "\n")
        receipt = json.loads(receipt_file.read_text())
        message = file.read_bytes()
        if archive.sha(message) != receipt["message_sha256"]:
            raise ValueError("Preserved NOAA field checksum changed")
        with file.open("rb") as source_file:
            gid = eccodes.codes_grib_new_from_file(source_file)
        try:
            metadata = {
                name: eccodes.codes_get(gid, name)
                for name in [
                    "dataDate",
                    "dataTime",
                    "forecastTime",
                    "validityDate",
                    "validityTime",
                    "shortName",
                    "typeOfLevel",
                    "level",
                    "stepType",
                    "units",
                ]
            }
            valid = dt + timedelta(hours=lead)
            if (
                metadata["dataDate"] != int(dt.strftime("%Y%m%d"))
                or metadata["dataTime"] != dt.hour * 100
                or metadata["forecastTime"] != lead
                or metadata["validityDate"] != int(valid.strftime("%Y%m%d"))
                or metadata["validityTime"] != valid.hour * 100
                or metadata["shortName"] != "2t"
                or metadata["typeOfLevel"] != "heightAboveGround"
                or metadata["level"] != 2
                or metadata["stepType"] != "instant"
                or metadata["units"] != "K"
            ):
                raise ValueError(
                    "Native source is not the requested instantaneous two-metre forecast"
                )
            # Decode one bounded field, then sample its native grid in Python.
            field = eccodes.codes_get_values(gid)
            if model == "GFS":
                nx = eccodes.codes_get(gid, "Ni")
                if eccodes.codes_get(gid, "scanningMode") != 0:
                    raise ValueError("Unsupported native GFS scan order")
                latitudes = eccodes.codes_get_array(gid, "distinctLatitudes")
                longitudes = eccodes.codes_get_array(gid, "distinctLongitudes")
                nearest = []
                for station in stations:
                    y = int(np.argmin(abs(latitudes - float(station["latitude"]))))
                    distance = abs(
                        (longitudes - float(station["longitude"]) + 180) % 360 - 180
                    )
                    x = int(np.argmin(distance))
                    nearest.append(
                        {
                            "lat": float(latitudes[y]),
                            "lon": float(longitudes[x]),
                            "value": float(field[y * nx + x]),
                        }
                    )
            else:
                grid = {
                    k: eccodes.codes_get(gid, k)
                    for k in [
                        "Nx",
                        "Ny",
                        "DxInMetres",
                        "DyInMetres",
                        "latitudeOfFirstGridPointInDegrees",
                        "longitudeOfFirstGridPointInDegrees",
                        "scanningMode",
                        "radiusInMetres",
                        "LaDInDegrees",
                        "LoVInDegrees",
                        "Latin1InDegrees",
                        "Latin2InDegrees",
                    ]
                }
                if grid["scanningMode"] != 64:
                    raise ValueError("Unsupported native HRRR scan order")
                projection = pyproj.Proj(
                    f"+proj=lcc +lat_1={grid['Latin1InDegrees']} +lat_2={grid['Latin2InDegrees']} "
                    f"+lat_0={grid['LaDInDegrees']} +lon_0={grid['LoVInDegrees']} "
                    f"+R={grid['radiusInMetres']} +units=m"
                )
                ox, oy = projection(
                    grid["longitudeOfFirstGridPointInDegrees"],
                    grid["latitudeOfFirstGridPointInDegrees"],
                )
                coordinates = []
                indices = []
                for station in stations:
                    px, py = projection(
                        float(station["longitude"]), float(station["latitude"])
                    )
                    x = math.floor((px - ox) / grid["DxInMetres"] + 0.5)
                    y = math.floor((py - oy) / grid["DyInMetres"] + 0.5)
                    lon, lat = projection(
                        ox + x * grid["DxInMetres"],
                        oy + y * grid["DyInMetres"],
                        inverse=True,
                    )
                    indices.append(y * grid["Nx"] + x)
                    coordinates.append((lat, lon))
                values = field[indices]
                nearest = [
                    {"lat": lat, "lon": lon, "value": float(value)}
                    for (lat, lon), value in zip(coordinates, values)
                ]
                metadata["native_grid"] = grid
        finally:
            eccodes.codes_release(gid)
        data = archive.points(record)
        idx = [archive.stamp(t) for t in data["valid_times"]].index(valid.timestamp())
        points = {p["cli"]: p for p in data["points"]}
        comparisons = []
        for station, native in zip(stations, nearest):
            point = points[station["cli"]]
            value = float(native["value"]) - 273.15
            stored = point["values_c"][idx]
            difference = stored - value
            comparisons.append(
                {
                    "city": station["city"],
                    "station": station["icao"],
                    "native_latitude": native["lat"],
                    "native_longitude": ((native["lon"] + 180) % 360) - 180,
                    "native_c": value,
                    "stored_c": stored,
                    "difference_c": difference,
                }
            )
        maxdiff = max(abs(r["difference_c"]) for r in comparisons)
        if maxdiff > 0.051:
            raise ValueError(
                f"{model} {dt}: archived and native values differ by {maxdiff} Celsius"
            )
        output.append(
            {
                "model": model,
                "run": record["run"],
                "valid_time": valid.isoformat(),
                **receipt,
                "grib_metadata": metadata,
                "comparisons": comparisons,
                "maximum_difference_c": maxdiff,
            }
        )
        print(
            "NOAA check",
            model,
            dt.isoformat(),
            "24 stations; maximum Celsius difference",
            round(maxdiff, 6),
            flush=True,
        )
    result = {
        "status": "passed",
        "checked_runs": len(output),
        "station_value_checks": sum(len(r["comparisons"]) for r in output),
        "tolerance_c": 0.051,
        "scope": "First, middle and final study dates, both cycles and both models; archive storage quantization allowed",
        "checks": output,
    }
    (ROOT / "reports/noaa-source-checks.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    return result
