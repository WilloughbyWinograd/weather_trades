"""End-to-end source and cash audit over real public records."""

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_CEILING
from urllib.parse import urlparse
from .http import ROOT, CACHE
from .forecasts import settings, days, station_rows
from .markets import weather_series
from .simulator import rows, contains
from .fees import units
from .evidence import load


def verify():
    cfg = settings()
    checks = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    snapshot_markets, _, snapshot_quotes = load()
    raw_quotes = defaultdict(dict)
    for path in CACHE.glob("*.meta"):
        metadata = json.loads(path.read_text())
        urlpath = urlparse(metadata["url"]).path
        if not urlpath.endswith("/candlesticks"):
            continue
        ticker = urlpath.split("/")[-2]
        if ticker not in snapshot_quotes:
            continue
        for candle in json.loads(path.with_suffix(".json").read_text())["candlesticks"]:
            values = (
                candle["yes_bid"].get("close_dollars"),
                candle["yes_ask"].get("close_dollars"),
                candle["yes_ask"].get("high_dollars"),
                candle.get("volume_fp", "0"),
            )
            raw_quotes[ticker].setdefault(candle["end_period_ts"], set()).add(values)
    for ticker, candles in snapshot_quotes.items():
        check(
            "Snapshot quotes equal original provider responses",
            all(
                (
                    c["yes_bid"]["close_dollars"],
                    c["yes_ask"]["close_dollars"],
                    c["yes_ask"]["high_dollars"],
                    c["volume_fp"],
                )
                in raw_quotes[ticker].get(c["end_period_ts"], set())
                for c in candles
            ),
        )
    classification = rows("config/market-classification.csv")
    check(
        "Every discovered weather series classified exactly once",
        Counter(r["series"] for r in classification)
        == Counter(s["ticker"] for s in weather_series()),
    )
    markets = json.loads((ROOT / "data/raw/markets.json").read_text())
    market_by_id = {m["ticker"]: m for m in markets}
    check("Market identifiers unique", len(market_by_id) == len(markets))
    check(
        "Replay snapshot covers exactly the acquired markets",
        {m["ticker"] for m in snapshot_markets} == set(market_by_id),
    )
    events = defaultdict(list)
    for m in markets:
        events[m["event_ticker"]].append(m)
    check(
        "Settlement outcomes agree with reported expiration values",
        all(
            sum(m["result"] == "yes" for m in ms) == 1
            and all(
                contains(m, float(m["expiration_value"])) == (m["result"] == "yes")
                for m in ms
            )
            for ms in events.values()
        ),
    )
    forecasts = rows("reports/forecast-samples.csv")
    stations = station_rows()
    expected = len(list(days(cfg["study_start"], cfg["study_end"]))) * len(stations) * 8
    forecast_keys = [
        (r["cli"], r["date"], r["model"], r["run_hour"], r["day_basis"])
        for r in forecasts
    ]
    check(
        "Entire requested forecast matrix present exactly once",
        len(forecasts) == expected == len(set(forecast_keys)),
    )
    from .verify_archive import audit as audit_archive

    max_grid_distance_km = audit_archive(forecasts, stations, check)
    from .noaa_check import run as verify_native

    native = verify_native(offline=True)
    check(
        "Native NOAA checks cover both models, cycles, and date boundaries",
        native["status"] == "passed"
        and native["checked_runs"] == 12
        and native["station_value_checks"] == 288,
    )
    check(
        "Station grid extraction remains local",
        max_grid_distance_km["GFS"] < 50 and max_grid_distance_km["HRRR"] < 10,
    )
    accuracy = rows("reports/accuracy.csv")
    counts = Counter((r["event"], r["model"]) for r in accuracy)
    check(
        "Accuracy paired on identical city-days",
        all(
            counts[(e, m)] == 1
            for e in {r["event"] for r in accuracy}
            for m in cfg["models"]
        ),
    )
    summaries = json.loads((ROOT / "reports/results.json").read_text())
    for summary in summaries:
        model, scenario = summary["model"], summary["scenario"]
        label = model + " " + scenario + ": "
        ledger = rows("reports/ledger-" + model + "-" + scenario + ".csv")
        trades = [r for r in ledger if r["status"] == "filled assumption"]
        check(label + "trade count", len(trades) == summary["trades"])
        check(
            label + "dollar reconciliation",
            abs(sum(float(r["profit"]) for r in trades) - summary["net_profit"]) < 1e-7
            and abs(100 + summary["net_profit"] - summary["ending_cash"]) < 1e-7,
        )
        check(
            label + "no duplicate city-day trades",
            len({(r["city"], r["date"]) for r in trades}) == len(trades),
        )
        check(
            label + "entry after forecast and before close and settlement",
            all(
                float(r["entry_ts"])
                > float(r["decision_ts"])
                >= max(
                    datetime.fromisoformat(r["previous_available_at"]).timestamp(),
                    datetime.fromisoformat(r["current_available_at"]).timestamp(),
                )
                + cfg["processing_buffer_seconds"]
                and float(r["entry_ts"])
                < min(
                    float(r["settlement_ts"]),
                    datetime.fromisoformat(
                        market_by_id[r["market"]]["close_time"].replace("Z", "+00:00")
                    ).timestamp(),
                )
                for r in trades
            ),
        )
        check(
            label + "entry budget and nonnegative cash",
            all(
                float(r["cost"]) + float(r["fee"]) <= 5 + 1e-9
                and (scenario == "unconstrained" or float(r["cash_after_entry"]) >= 0)
                for r in trades
            ),
        )
        archive_records = {
            (r["model"], r["run"]): r
            for r in json.loads((ROOT / "reports/archive-runs.json").read_text())
            if r["status"] == "complete"
        }
        for row in ledger:
            previous = archive_records[(model, row["previous_run"])]
            current = archive_records[(model, row["run"])]
            ready = max(
                datetime.fromisoformat(previous["available_at"]).timestamp(),
                datetime.fromisoformat(current["available_at"]).timestamp(),
            )
            check(
                label
                + "every accepted or rejected signal has actual publication evidence",
                row["previous_source_etag"] == previous["data_object"]["etag"]
                and row["current_source_etag"] == current["data_object"]["etag"]
                and float(row["decision_ts"])
                >= ready + cfg["processing_buffer_seconds"],
            )
        for r in trades:
            quantity, price = int(r["quantity"]), Decimal(r["price"])
            quantum = Decimal("0.01" if scenario == "cent_fees" else "0.0001")
            total = (
                (quantity * price + Decimal("0.07") * quantity * price * (1 - price))
                / quantum
            ).to_integral_value(rounding=ROUND_CEILING) * quantum
            check(
                label + "fees independently calculated",
                abs(total - Decimal(r["cost"]) - Decimal(r["fee"]))
                < Decimal("0.0000001"),
            )
            check(
                label + "payout follows actual settlement",
                float(r["payout"])
                == (quantity if market_by_id[r["market"]]["result"] == "yes" else 0),
            )
            candle = next(
                c
                for c in snapshot_quotes[r["market"]]
                if c["end_period_ts"] == float(r["entry_ts"])
            )
            conservative = scenario in {
                "conservative",
                "evaluation_conservative",
                "volume_capped",
                "evaluation_volume_capped",
            }
            ask = float(
                candle["yes_ask"]["high_dollars" if conservative else "close_dollars"]
            )
            expected_price = round(ask + 0.02, 4) if conservative else ask
            check(
                label + "entry uses the recorded ask",
                float(r["price"]) == expected_price
                and (not conservative or float(candle["volume_fp"]) > 0),
            )
            if scenario in {"volume_capped", "evaluation_volume_capped"}:
                check(
                    label + "quantity is capped by observed interval volume",
                    quantity <= int(float(candle["volume_fp"])),
                )
        if scenario != "unconstrained":
            stream = []
            for r in trades:
                stream.extend(
                    [
                        (float(r["entry_ts"]), 1, r["city"], r),
                        (float(r["settlement_ts"]), 0, r["city"], r),
                    ]
                )
            cash, active, valid = units(100), 0, True
            for _, kind, _, r in sorted(stream, key=lambda x: (x[0], x[1], x[2])):
                if kind:
                    cash -= units(r["cost"]) + units(r["fee"])
                    active += 1
                else:
                    cash += units(r["payout"])
                    active -= 1
                valid = valid and cash >= 0 and 0 <= active <= 5
            check(
                label + "chronological cash and position limits", valid and active == 0
            )
            check(
                label + "independently replayed cash",
                cash == units(summary["ending_cash"]),
            )
    manifest = rows("reports/source-manifest.csv")
    check(
        "Every source cache checksum matches manifest",
        all(
            hashlib.sha256(
                (CACHE / (r["cache_key"] + r["cache_suffix"])).read_bytes()
            ).hexdigest()
            == r["cache_sha256"]
            for r in manifest
        ),
    )
    check(
        "Every paired city in coverage ledger",
        {r["city"] for r in accuracy}
        <= {r["city"] for r in rows("reports/coverage.csv")},
    )
    record = {
        "status": "passed",
        "verification_scope": "Original run-file bytes, completed-run publication, post-publication entries, and simulation arithmetic",
        "historical_forecast_accessibility": "verified for the exact public run-file source before simulated entry; not a claim about the historical forecast API",
        "verified_forecast_source_before_entry": True,
        "historical_executable_fills": "unverified; quoted fills assumed",
        "verified_exact_live_replay": False,
        "assertions": len(checks),
        "distinct_assertions": len(set(checks)),
        "markets": len(markets),
        "city_days": len(events),
        "forecast_reductions": len(forecasts),
        "paired_forecasts": len(accuracy),
        "source_responses": len(manifest),
        "maximum_station_grid_distance_km": dict(max_grid_distance_km),
        "constraints": "Real source records, independent forecast reduction, fee calculation and chronological cash replay; no synthetic performance data",
    }
    (ROOT / "reports/verification.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return record


if __name__ == "__main__":
    verify()
