"""Reproducible performance, coverage, accuracy, and source reports."""

import hashlib
import json
import statistics
from collections import defaultdict
from datetime import datetime
from .http import ROOT, CACHE
from .simulator import rows
from .markets import write_csv, weather_series
from .forecasts import settings


def accuracy_statistics(records):
    return {
        "paired_days": len(records),
        "mean_absolute_error_f": statistics.mean(
            float(r["absolute_error_f"]) for r in records
        ),
        "bias_f": statistics.mean(float(r["error_f"]) for r in records),
        "correct_outcome_rate": statistics.mean(
            int(r["correct_outcome"]) for r in records
        ),
    }


def build():
    cfg = settings()
    result = json.loads((ROOT / "reports/results.json").read_text())
    archive_runs = json.loads((ROOT / "reports/archive-runs.json").read_text())
    accuracy = rows("reports/accuracy.csv")
    ledgers = {m: rows("reports/ledger-" + m + "-baseline.csv") for m in cfg["models"]}
    citygroups = defaultdict(list)
    for r in accuracy:
        citygroups[(r["model"], r["city"], r["station"])].append(r)
    cityresults = []
    for (model, city, station), records in sorted(citygroups.items()):
        trades = [
            r
            for r in ledgers[model]
            if r["city"] == city and r["status"] == "filled assumption"
        ]
        cityresults.append(
            {
                "model": model,
                "city": city,
                "station": station,
                **accuracy_statistics(records),
                "trades": len(trades),
                "net_profit": sum(float(r["profit"]) for r in trades),
                "fees": sum(float(r["fee"]) for r in trades),
                "wins": sum(r["winner"] == "True" for r in trades),
            }
        )
    write_csv("reports/by-city.csv", cityresults)
    for dimension, key in [
        ("phase", lambda r: r["phase"]),
        ("month", lambda r: r["date"][:7]),
    ]:
        groups = defaultdict(list)
        for r in accuracy:
            groups[(r["model"], key(r))].append(r)
        write_csv(
            "reports/accuracy-by-" + dimension + ".csv",
            [
                {"model": model, dimension: value, **accuracy_statistics(records)}
                for (model, value), records in sorted(groups.items())
            ],
        )
    inventory = rows("reports/city-inventory.csv")
    acquisition = {r["series"]: r for r in rows("reports/market-acquisition.csv")}
    covered = {r["city"] for r in accuracy}
    coords = {r["city"].split(" (")[0]: r for r in rows("config/stations.csv")}
    coverage = []
    for r in inventory:
        city = r["city"]
        count = sum(
            int(acquisition[s]["markets"])
            for s in r["series"].split(";")
            if s in acquisition
        )
        if city in covered:
            status = "included paired backtest"
        elif count:
            status = "market present; see station or forecast exclusions"
        elif "daily high" in r["product_classes"]:
            status = "no settled daily-high contract in study window"
        else:
            status = "outside daily-high strategy"
        st = coords.get(city, {})
        coverage.append(
            {
                **r,
                "status": status,
                "daily_high_markets": count,
                "station": st.get("icao", ""),
                "latitude": st.get("latitude", ""),
                "longitude": st.get("longitude", ""),
                "coordinate_source": st.get("coordinate_source", ""),
                "coordinate_status": "verified for study station"
                if st
                else "not mapped; no eligible daily-high contract",
                "hrrr": "evaluated"
                if city in covered
                else "not evaluated; no eligible paired sample",
            }
        )
    write_csv("reports/coverage.csv", coverage)
    forecast_groups = defaultdict(list)
    for r in rows("reports/forecast-samples.csv"):
        forecast_groups[
            (r["model"], r["station"], r["run_hour"], r["day_basis"])
        ].append(r)
    availability = []
    for (model, station, hour, basis), records in sorted(forecast_groups.items()):
        leads = [
            (
                datetime.fromisoformat(r["last_valid"])
                - datetime.fromisoformat(r["run"])
            ).total_seconds()
            / 3600
            for r in records
        ]
        availability.append(
            {
                "model": model,
                "station": station,
                "run_hour_utc": hour,
                "day_basis": basis,
                "first_date": min(r["date"] for r in records),
                "last_date": max(r["date"] for r in records),
                "requested_days": len(records),
                "complete_days": sum(r["status"] == "complete" for r in records),
                "minimum_final_lead_hours": min(leads),
                "maximum_final_lead_hours": max(leads),
                "publication_evidence": "exact public run objects and completed-run markers; missing run excluded",
                "minimum_publication_lag_hours": min(
                    (
                        datetime.fromisoformat(r["available_at"])
                        - datetime.fromisoformat(r["run"])
                    ).total_seconds()
                    / 3600
                    for r in records
                    if r.get("available_at")
                ),
                "maximum_publication_lag_hours": max(
                    (
                        datetime.fromisoformat(r["available_at"])
                        - datetime.fromisoformat(r["run"])
                    ).total_seconds()
                    / 3600
                    for r in records
                    if r.get("available_at")
                ),
                "source_product": records[0]["source_model"],
                "source": cfg["forecast_source"],
            }
        )
    write_csv("reports/source-availability.csv", availability)
    manifests = []
    for p in sorted(CACHE.glob("*.meta")):
        m = json.loads(p.read_text())
        cache = p.with_suffix(m.get("cache_suffix", ".json"))
        sha = hashlib.sha256(cache.read_bytes()).hexdigest()
        manifests.append(
            {
                "cache_key": p.stem,
                "cache_suffix": cache.suffix,
                "status": m.get("error", "available"),
                "request_url": m["url"],
                "retrieved_at_unix": m["retrieved_at"],
                "source_sha256": m["sha256"],
                "cache_sha256": sha,
                "bytes": cache.stat().st_size,
                "cache_format": "original response"
                if sha == m["sha256"]
                else "normalized JSON from initial probe",
            }
        )
    write_csv("reports/source-manifest.csv", manifests)
    write_csv(
        "reports/forecast-timing.csv",
        [
            {
                "model": r["model"],
                "run": r["run"],
                "status": r["status"],
                "source_url": r.get("data_object", {}).get(
                    "url", r.get("data_url", "")
                ),
                "source_etag": r.get("data_object", {}).get("etag", ""),
                "source_modified": r.get("data_object", {}).get("last_modified", ""),
                "completion_url": r.get("completion_object", {}).get(
                    "url", r.get("metadata_url", "")
                ),
                "completion_etag": r.get("completion_object", {}).get("etag", ""),
                "available_at": r.get("available_at", ""),
            }
            for r in archive_runs
        ],
    )
    native = json.loads((ROOT / "reports/noaa-source-checks.json").read_text())
    publication_lines = []
    for model in cfg["models"]:
        runs = [
            r
            for r in archive_runs
            if r["model"] == model
            and r["status"] == "complete"
            and datetime.fromisoformat(r["run"]).hour == cfg["current_cycle_utc_hour"]
        ]
        lag = [
            (
                datetime.fromisoformat(r["available_at"])
                - datetime.fromisoformat(r["run"])
            ).total_seconds()
            / 3600
            for r in runs
        ]
        publication_lines.append(
            f"| {model} | {len(runs)} | {min(lag):.2f} | {statistics.median(lag):.2f} | {max(lag):.2f} |"
        )
    lookup = {(r["model"], r["scenario"]): r for r in result}
    lines = [
        "# GFS versus HRRR: corrected forecast timing",
        "",
        f"Study: {cfg['study_start']} through {cfg['study_end']}. Each model starts with $100 shared across cities.",
        "No real orders, purchases, deposits, or new paid infrastructure were used.",
        "",
        "**Forecast source availability is verified before simulated entries. Trade fills remain assumptions.**",
        "The program reads the original public run files directly. It uses the exact stored temperature values and each run's completion marker.",
        "These are operational forecasts, not reanalysis or later runs. This source path avoids assumptions about historical forecast API updates.",
        "Each model acts after its own publication: the next one-minute poll, one minute for processing, and the declared execution delay.",
        "The shared-time scenario waits until both models' files are available. Timing rules were fixed before calculating corrected returns.",
        "See [every run's publication evidence](forecast-timing.csv), [source records](archive-runs.json), and [native NOAA checks](noaa-source-checks.json).",
        "The one missing GFS run remains excluded from both models. No release time or forecast is fabricated for it.",
        "",
        "## Verified source timing",
        "",
        "Publication lags below cover the 18:00 UTC runs used for new signals. Every previous run is also checked.",
        "",
        "| Model | Complete current runs | Minimum lag (hours) | Median lag (hours) | Maximum lag (hours) |",
        "| --- | ---: | ---: | ---: | ---: |",
        *publication_lines,
        "",
        "The late September 22 GFS run becomes eligible after its September 23 00:41:11 UTC completion marker, never at the former 23:00 UTC decision.",
        f"Native NOAA checks passed for {native['checked_runs']} fields and {native['station_value_checks']} station values. Maximum temperature difference: {max(r['maximum_difference_c'] for r in native['checks']):.6f} degree Celsius.",
        "The correction preserves stored temperature precision and uses NOAA's precise HRRR grid origin. This also corrects Trenton's selected cell.",
        "",
        "## Reserved evaluation: September 25–October 8",
        "",
        "These dates were reserved in the original protocol. This is a corrected rerun of previously viewed dates, not a new untouched evaluation.",
        "The trade rule, price limits, fees, and portfolio limits remain unchanged. The source precision and publication timing are corrected.",
        "",
        "| Model | Ending balance | Net profit | Trades | Wins | Fees |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for model in cfg["models"]:
        r = lookup[(model, "evaluation")]
        lines.append(
            f"| {model} | ${r['ending_cash']:.2f} | ${r['net_profit']:.2f} | {r['trades']} | {r['wins']} | ${r['fees']:.2f} |"
        )
    lines += [
        "",
        "## Full study: quoted-price scenario",
        "",
        "| Model | Ending balance | Net profit | Trades | Wins | Fees | Maximum drawdown at cost |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for model in cfg["models"]:
        r = lookup[(model, "baseline")]
        lines.append(
            f"| {model} | ${r['ending_cash']:.2f} | ${r['net_profit']:.2f} | {r['trades']} | {r['wins']} | ${r['fees']:.2f} | ${r['maximum_drawdown_at_cost']:.2f} |"
        )
    lines += [
        "",
        "These are simulated quoted fills after fees. Historical executable quantities are unknown.",
        "Open positions are valued at purchase cost for drawdown. This does not measure changes in their resale value.",
        "",
        "## Coverage",
        "",
        f"The study includes {len(covered)} cities and {len(accuracy) // 2:,} paired city-days.",
        f"The inventory classifies {len(weather_series())} weather series and records {len(inventory)} named cities or resort locations.",
        "It combines current and retired series with all retrieved location-variable products.",
        "Every discovered location remains in [coverage.csv](coverage.csv), with its eligibility and coordinate status.",
        "Cities with only other weather products have no daily-high return. Empty international series cannot support a return estimate.",
        "This is the initial six-week comparison, not the complete historical archive.",
        "",
        "## Forecast accuracy",
        "",
        "| Model | Period | Mean absolute error (degrees Fahrenheit) | Bias (degrees Fahrenheit) | Correct outcome |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for model in cfg["models"]:
        for phase in ["all", "evaluation"]:
            records = [
                r
                for r in accuracy
                if r["model"] == model and (phase == "all" or r["phase"] == phase)
            ]
            a = accuracy_statistics(records)
            lines.append(
                f"| {model} | {phase} | {a['mean_absolute_error_f']:.3f} | {a['bias_f']:.3f} | {a['correct_outcome_rate']:.1%} |"
            )
    lines += [
        "",
        "## Sensitivity and portfolio constraints",
        "",
        "| Model | Scenario | Ending balance | Trades | Net profit |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for r in result:
        if r["scenario"] != "baseline":
            balance = (
                "Not a $100 portfolio"
                if r["scenario"] == "unconstrained"
                else f"${r['ending_cash']:.2f}"
            )
            lines.append(
                f"| {r['model']} | {r['scenario']} | {balance} | {r['trades']} | ${r['net_profit']:.2f} |"
            )
    lines += [
        "",
        "The conservative scenario adds two cents, uses the highest ask, and requires positive interval volume. It still assumes a fill.",
        "The volume-capped scenario also limits purchases to that minute's reported volume. This remains an assumed fill, not historical depth.",
        "Zero fills leave either account at $100. Volume does not establish that our order could have filled.",
        "Each independent phase starts at $100. The unconstrained diagnostic ignores cash and position limits; its aggregate profit requires more capital.",
        "The baseline allows five open positions and spends at most $5 per trade, including fees.",
        "Capital stays locked until recorded settlement. Simultaneous entries sort by city name, so allocation is unequal across cities.",
        "",
        "## Every included city",
        "",
        "| City | Station | Paired days | GFS error (degrees Fahrenheit) | HRRR error (degrees Fahrenheit) | GFS trades / profit | HRRR trades / profit |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    citylookup = {(r["model"], r["city"]): r for r in cityresults}
    for city in sorted(covered):
        g, h = citylookup[("GFS", city)], citylookup[("HRRR", city)]
        lines.append(
            f"| {city} | {g['station']} | {g['paired_days']} | {g['mean_absolute_error_f']:.2f} | {h['mean_absolute_error_f']:.2f} | {g['trades']} / ${g['net_profit']:.2f} | {h['trades']} / ${h['net_profit']:.2f} |"
        )
    lines += [
        "",
        "City profits are contributions to the shared portfolio. They are not independent $100 city portfolios.",
        "",
        "## Interpretation and remaining work",
        "",
        "This experiment compares a fixed forecast-revision rule against archived forecasts, later quotes, and settled outcomes.",
        "Forecast accuracy and trading profit are separate results. A model can improve one without improving the other.",
        "The short period and correlated weather across cities prevent a reliable long-term profitability conclusion.",
        "Every consumed run file and completion marker predates its simulated decision. The saved binary ranges reproduce the extracted values exactly.",
        "Publication evidence applies to direct public archive access. Historical API routing and client download logs are not required by this source path.",
        "Polling, processing, and order latency remain simulated. This study does not establish an advantage that lasts only seconds.",
        "Forecasts use hourly maxima at the settlement station coordinates. Hourly values can miss brief temperature extremes.",
        "Station coordinates use current metadata. Historical relocations and source-day definitions require further auditing.",
        "The study compares the previous day's 12 and 18 UTC runs. HRRR's intervening short runs cannot cover the complete target day.",
        "Earlier history, other daily update pairs, and live executable depth remain separate extensions.",
        "",
        "## Reproduce and inspect",
        "",
        "Run `python -m weather_trades.cli replay` after installation for an offline replay of the compact saved inputs.",
        "See [methodology](../docs/methodology.md), [exact results](results.json), [city results](by-city.csv), and [source requests](source-manifest.csv).",
        "The ledger files contain every accepted and rejected signal. Forecast and source-availability files retain timing and station information.",
        "Source attribution: Open-Meteo, NOAA GFS, NOAA HRRR, Kalshi, and The Weather Company.",
    ]
    (ROOT / "reports/summary.md").write_text("\n".join(lines) + "\n")
    return result


if __name__ == "__main__":
    build()
