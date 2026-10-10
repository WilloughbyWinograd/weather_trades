"""Tweet entry signals and subsequent quoted price changes, without a portfolio."""

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
import math
import statistics
from urllib.parse import parse_qs, urlparse

from .archive import publication_time
from .evidence import digest
from .history import candles, quote, timestamp
from .http import ROOT, BASE, CACHE, cache_key, get
from .markets import write_csv
from .simulator import contains, rounded, rows

DIRECTORY = ROOT / "reports/tweet-price-response"
CONFIG = "config/tweet-price-response.json"
BOUND_FILES = [
    CONFIG,
    "reports/forecast-samples.csv",
    "reports/archive-runs.json",
    "reports/station-validation.csv",
    "config/stations.csv",
    "reports/replay-inputs.json",
    "reports/source-manifest.csv",
]
MARKET_FIELDS = [
    "ticker",
    "event_ticker",
    "series_ticker",
    "strike_type",
    "floor_strike",
    "cap_strike",
    "created_time",
    "open_time",
    "close_time",
]


def settings():
    return json.loads((ROOT / CONFIG).read_text())


def make_signals(markets):
    cfg = settings()
    forecasts = {
        (r["cli"], r["date"], r["model"], int(r["run_hour"])): r
        for r in rows("reports/forecast-samples.csv")
        if r["status"] == "complete" and r["day_basis"] == cfg["day_basis"]
    }
    archive = {
        (r["model"], r["run"]): r
        for r in json.loads((ROOT / "reports/archive-runs.json").read_text())
        if r["status"] == "complete"
    }
    for f in forecasts.values():
        a = archive[(f["model"], f["run"])]
        if (
            timestamp(f["available_at"]) != publication_time(a)
            or f["source_url"] != a["data_object"]["url"]
            or f["source_etag"] != a["data_object"]["etag"]
            or f["completion_etag"] != a["completion_object"]["etag"]
        ):
            raise ValueError("Forecast publication evidence mismatch")
    events = defaultdict(list)
    for m in markets:
        if set(m) - set(MARKET_FIELDS):
            raise ValueError("Decision inputs contain unapproved market fields")
        events[m["event_ticker"]].append(m)
    signals = []
    exclusions = []
    paired = []
    for v in sorted(rows("reports/station-validation.csv"), key=lambda x: x["event"]):
        if (
            not v["status"].startswith("verified")
            or not cfg["study_start"] <= v["date"] <= cfg["study_end"]
        ):
            continue
        keys = [
            (v["cli"], v["date"], model, h)
            for model in cfg["models"]
            for h in [cfg["previous_cycle_utc_hour"], cfg["current_cycle_utc_hour"]]
        ]
        if any(k not in forecasts for k in keys):
            exclusions.append(
                {"event": v["event"], "reason": "paired forecast unavailable"}
            )
            continue
        paired.append(v["event"])
        for model in cfg["models"]:
            before, after = [
                forecasts[(v["cli"], v["date"], model, h)]
                for h in [cfg["previous_cycle_utc_hour"], cfg["current_cycle_utc_hour"]]
            ]
            previous = float(before["high_c"])
            current = float(after["high_c"])
            revision = current - previous
            if abs(revision) + 1e-10 < cfg["minimum_revision_celsius"]:
                continue
            ready = max(
                timestamp(before["available_at"]), timestamp(after["available_at"])
            )
            decision = (
                math.ceil(ready / cfg["poll_seconds"]) * cfg["poll_seconds"]
                + cfg["processing_buffer_seconds"]
            )
            target_c = rounded(previous) + (1 if revision > 0 else -1)
            target_f = rounded(target_c * 1.8 + 32)
            matches = [m for m in events[v["event"]] if contains(m, target_f)]
            s = {
                "model": model,
                "city": v["city"].split(" (")[0],
                "station": v["station"],
                "date": v["date"],
                "event": v["event"],
                "previous_run": before["run"],
                "current_run": after["run"],
                "previous_high_c": previous,
                "current_high_c": current,
                "revision_c": revision,
                "target_c": target_c,
                "target_integer_f": target_f,
                "decision_ts": decision,
                "previous_available_at": before["available_at"],
                "current_available_at": after["available_at"],
                "previous_source_etag": before["source_etag"],
                "current_source_etag": after["source_etag"],
                "previous_source_url": before["source_url"],
                "current_source_url": after["source_url"],
                "status": "candidate",
            }
            if decision >= timestamp(after["first_valid"]):
                s["status"] = "not ready before target day"
            elif len(matches) != 1:
                s["status"] = "target has no unique bracket"
            else:
                m = matches[0]
                s.update(market=m["ticker"], close_ts=timestamp(m["close_time"]))
                if (
                    max(timestamp(m["created_time"]), timestamp(m["open_time"]))
                    > decision
                ):
                    s["status"] = "market not open at decision"
                elif decision >= s["close_ts"]:
                    s["status"] = "market already closed"
            signals.append(s)
    return signals, exclusions, paired


def source_receipt(url, params=None):
    key = cache_key(url, params)
    path = CACHE / (key + ".json")
    receipt = json.loads(path.with_suffix(".meta").read_text())
    cached_sha = digest(path)
    cache_format = "original response bytes"
    if cached_sha != receipt["sha256"]:
        # Initial inventory probes stored normalized JSON. Accept only the
        # exact normalized version already pinned by the published manifest.
        matches = [
            r
            for r in rows("reports/source-manifest.csv")
            if r["cache_key"] == key
            and r["source_sha256"] == receipt["sha256"]
            and r["cache_sha256"] == cached_sha
        ]
        if len(matches) != 1:
            raise ValueError("Public response checksum mismatch")
        cache_format = matches[0]["cache_format"]
    return {
        "cache_key": key,
        **receipt,
        "cache_sha256": cached_sha,
        "cache_format": cache_format,
    }


def acquire():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    original = json.loads((ROOT / "reports/replay-inputs.json").read_text())["markets"]
    markets = [{k: m[k] for k in MARKET_FIELDS if k in m} for m in original]
    signals, _, _ = make_signals(markets)
    by_ticker = {m["ticker"]: m for m in original}
    cfg = settings()
    windows = sorted(
        {
            (
                s["market"],
                s["decision_ts"],
                s["decision_ts"]
                + (
                    cfg["execution_delay_minutes"]
                    + 1
                    + cfg["quote_max_wait_minutes"]
                    + max(cfg["horizons_minutes"])
                )
                * 60,
            )
            for s in signals
            if s["status"] == "candidate"
        }
    )
    cutoff = get(BASE + "/historical/cutoff")

    def fetch(window):
        ticker, start, end = window
        m = by_ticker[ticker]
        data = candles(m, start, end)
        archived = timestamp(m["settlement_ts"]) < timestamp(
            cutoff["market_settled_ts"]
        )
        suffix = (
            "/historical/markets/" + ticker + "/candlesticks"
            if archived
            else "/series/"
            + m["series_ticker"]
            + "/markets/"
            + ticker
            + "/candlesticks"
        )
        params = {"start_ts": int(start), "end_ts": int(end), "period_interval": 1}
        compact = [
            [
                c["end_period_ts"],
                c.get("yes_bid", {}).get("close_dollars"),
                c.get("yes_ask", {}).get("close_dollars"),
                c.get("volume_fp", "0"),
            ]
            for c in data
        ]
        return {
            "market": ticker,
            "start_ts": start,
            "end_ts": end,
            "source": source_receipt(BASE + suffix, params),
            "candles": compact,
        }

    samples = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        for i, window in enumerate(executor.map(fetch, windows), 1):
            samples.append(window)
            if i % 25 == 0:
                print("quote windows", i, "of", len(windows), flush=True)
    payload = {
        "schema_version": 1,
        "bound_files": {p: digest(ROOT / p) for p in BOUND_FILES},
        "cutoff_source": source_receipt(BASE + "/historical/cutoff"),
        "markets": markets,
        "quote_columns": [
            "end_period_ts",
            "yes_bid_close_dollars",
            "yes_ask_close_dollars",
            "volume_fp",
        ],
        "windows": samples,
    }
    (DIRECTORY / "inputs.json").write_text(
        json.dumps(payload, separators=(",", ":")) + "\n"
    )
    return run()


def load():
    p = json.loads((DIRECTORY / "inputs.json").read_text())
    if p["schema_version"] != 1 or set(p["bound_files"]) != set(BOUND_FILES):
        raise ValueError("Unsupported or incomplete price-response inputs")
    for name, sha in p["bound_files"].items():
        if digest(ROOT / name) != sha:
            raise ValueError("Changed price-response input: " + name)
    quotes = defaultdict(dict)
    for w in p["windows"]:
        for t, bid, ask, volume in w["candles"]:
            q = {
                "end_period_ts": t,
                "yes_bid": {"close_dollars": bid},
                "yes_ask": {"close_dollars": ask},
                "volume_fp": volume,
            }
            previous = quotes[w["market"]].setdefault(t, q)
            if q != previous:
                raise ValueError("Conflicting historical quotes")
    return p, {
        m: sorted(q.values(), key=lambda c: c["end_period_ts"])
        for m, q in quotes.items()
    }


def change_cents(after, before):
    return float((Decimal(str(after)) - Decimal(str(before))) * 100)


def calculate(markets, candles_by_market):
    cfg = settings()
    signals, exclusions, paired = make_signals(markets)
    samples = []
    for s in signals:
        if s["status"] != "candidate":
            continue
        cs = candles_by_market.get(s["market"], [])
        q = quote(cs, s["decision_ts"], cfg["execution_delay_minutes"])
        if q is None:
            s["status"] = "no initial quote"
            continue
        s.update(
            initial_ts=q["entry_ts"],
            initial_ask=q["price"],
            initial_bid=q["bid"],
            initial_volume=q["volume"],
        )
        if q["entry_ts"] >= s["close_ts"]:
            s["status"] = "market closed before initial quote"
        elif not cfg["minimum_ask_dollars"] <= q["price"] <= cfg["maximum_ask_dollars"]:
            s["status"] = "initial ask outside band"
        else:
            s["status"] = "eligible"
            by_time = {c["end_period_ts"]: c for c in cs}
            for horizon in cfg["horizons_minutes"]:
                future_ts = q["entry_ts"] + horizon * 60
                r = {
                    "model": s["model"],
                    "city": s["city"],
                    "date": s["date"],
                    "market": s["market"],
                    "initial_ts": q["entry_ts"],
                    "initial_ask": q["price"],
                    "initial_bid": q["bid"],
                    "initial_volume": q["volume"],
                    "horizon_minutes": horizon,
                    "future_ts": future_ts,
                    "status": "missing future quote",
                }
                c = by_time.get(future_ts)
                if future_ts >= s["close_ts"]:
                    r["status"] = "market closed at horizon"
                elif (
                    c
                    and c["yes_bid"]["close_dollars"] is not None
                    and c["yes_ask"]["close_dollars"] is not None
                ):
                    bid, ask = (
                        float(c["yes_bid"]["close_dollars"]),
                        float(c["yes_ask"]["close_dollars"]),
                    )
                    if 0 <= bid <= ask <= 1:
                        r.update(
                            status="observed",
                            future_bid=bid,
                            future_ask=ask,
                            future_volume=float(c["volume_fp"]),
                            ask_change_cents=change_cents(ask, q["price"]),
                            later_bid_minus_initial_ask_cents=change_cents(
                                bid, q["price"]
                            ),
                        )
                samples.append(r)
    summaries = []
    for model in cfg["models"]:
        sig = [s for s in signals if s["model"] == model]
        for horizon in cfg["horizons_minutes"]:
            selected = [
                r
                for r in samples
                if r["model"] == model and r["horizon_minutes"] == horizon
            ]
            observed = [r for r in selected if r["status"] == "observed"]
            changes = [r["ask_change_cents"] for r in observed]
            summaries.append(
                {
                    "model": model,
                    "horizon_minutes": horizon,
                    "revision_signals": len(sig),
                    "eligible_initial_quotes": len(selected),
                    "observed": len(observed),
                    "missing": len(selected) - len(observed),
                    "mean_ask_change_cents": statistics.mean(changes)
                    if changes
                    else None,
                    "median_ask_change_cents": statistics.median(changes)
                    if changes
                    else None,
                    "risers": sum(v > 0 for v in changes),
                    "unchanged": sum(v == 0 for v in changes),
                    "fallers": sum(v < 0 for v in changes),
                    "mean_later_bid_minus_initial_ask_cents": statistics.mean(
                        r["later_bid_minus_initial_ask_cents"] for r in observed
                    )
                    if observed
                    else None,
                    "initial_zero_volume": sum(
                        r["initial_volume"] == 0 for r in observed
                    ),
                    "signal_statuses": dict(Counter(s["status"] for s in sig)),
                }
            )
    summary = {
        "paired_city_days": len(paired),
        "cities": len({s["city"] for s in signals}),
        "study_start": cfg["study_start"],
        "study_end": cfg["study_end"],
        "results": summaries,
    }
    return signals, samples, exclusions, summary


def run():
    p, qs = load()
    signals, samples, exclusions, summary = calculate(p["markets"], qs)
    for name, data in [
        ("signals", signals),
        ("samples", samples),
        ("exclusions", exclusions),
    ]:
        write_csv(DIRECTORY / (name + ".csv"), data)
    (DIRECTORY / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    report(summary)
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def report(summary):
    def cents(value):
        return "unavailable" if value is None else f"{value:+.2f}"

    lines = [
        "# Tweet-method price response",
        "",
        f"August 28–October 8, 2026; {summary['cities']} cities and {summary['paired_city_days']} paired city-days. Values below are average quoted ask-price changes, in cents per contract.",
        "",
        "| Model | After 15 minutes | Observations | After 60 minutes | Observations |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for model in settings()["models"]:
        a, b = [r for r in summary["results"] if r["model"] == model]
        lines.append(
            f"| {model} | {cents(a['mean_ask_change_cents'])} | {a['observed']} | {cents(b['mean_ask_change_cents'])} | {b['observed']} |"
        )
    lines += [
        "",
        "Exact-minute quotes are absent for many signals. Those missing observations are excluded from the averages, so these results describe only the observed subset.",
        "",
        "## Entry rule",
        "",
        "The [original tweet](https://x.com/xmayeth/status/2108586474715185534) describes buying after tomorrow's maximum temperature changes by at least 0.5 degrees Celsius. It selects the outcome one degree toward the new forecast and restricts the initial price to 5–60 cents. It supplies no exit rule.",
        "",
        "This Kalshi adaptation rounds the previous forecast to a whole Celsius degree, moves one Celsius degree in the revision direction, converts that target to Fahrenheit, and selects the bracket containing its rounded integer. Both roundings use half away from zero. This reproduces the tweet's 16.8-to-15.8 degree example by selecting 16 degrees Celsius. It does not require a change of Fahrenheit bracket.",
        "",
        "The existing 12:00-to-18:00 Coordinated Universal Time run pair is retained for each model, using the original archived forecast files. This is one update comparison per target day, not every model cycle or the tweet's complete Polymarket deployment. The existing validated city universe and local standard-day definitions are retained. The missing Global Forecast System run excludes September 15 for both models. These dates were analyzed before this retest; this is not a new untouched evaluation.",
        "",
        "## Timing and measurements",
        "",
        "Each model checks at the next whole hour after both consumed run files have completion markers, allows one minute for processing, then one minute before the first complete quote candle. The first valid quote is used within a five-minute wait; it is rejected if its ask is outside the price band. Forecasts must be ready before the target day and the selected contract must already be open.",
        "",
        "Later quotes are sampled exactly 15 and 60 minutes after the initial quote. There is no forward filling or selection by later price. Every eligible signal is retained, without cash or position limits. Prices are equally weighted across signals. No sale, portfolio return, fees, or executable quantity is assumed.",
        "",
        "| Model | Minutes | Observed / eligible | Median ask change | Later bid minus initial ask | Initial candles with zero volume |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in summary["results"]:
        lines.append(
            f"| {r['model']} | {r['horizon_minutes']} | {r['observed']}/{r['eligible_initial_quotes']} | {cents(r['median_ask_change_cents'])} | {cents(r['mean_later_bid_minus_initial_ask_cents'])} | {r['initial_zero_volume']} |"
        )
    lines += [
        "",
        "The bid-minus-ask column shows the average price gap after crossing the quoted spread. It is not realized profit. Zero-volume candles can contain quoted prices but do not demonstrate a trade or available size. Neither price movement nor this comparison establishes that the forecast caused the movement.",
        "",
        "## Evidence and reproduction",
        "",
        "[Frozen rules](../../config/tweet-price-response.json), [all signals and exclusions](signals.csv), [individual measurements](samples.csv), [paired-date exclusions](exclusions.csv), [complete summary](summary.json), [compact inputs and source receipts](inputs.json), and [verification](verification.json). Forecast identity and publication evidence remain in the [run manifest](../archive-runs.json) and [forecast table](../forecast-samples.csv).",
        "",
        "Run `python -m weather_trades.cli replay-tweet-prices` to reproduce the report from committed inputs without network access. `tweet-prices` reacquires public quotes; `verify-tweet-prices` additionally checks them against the local raw response cache and repeats the replay with network connections disabled.",
        "",
    ]
    (DIRECTORY / "summary.md").write_text("\n".join(lines))


def verify():
    """Verify actual saved quote responses, exact clocks, arithmetic and offline replay."""
    p, qs = load()
    original = json.loads((ROOT / "reports/replay-inputs.json").read_text())["markets"]
    assert p["markets"] == [
        {k: m[k] for k in MARKET_FIELDS if k in m} for m in original
    ]
    cfg = settings()
    assert (
        source_receipt(cfg["source_retrieval_url"])["sha256"]
        == cfg["source_response_sha256"]
    )
    for w in p["windows"]:
        receipt = w["source"]
        url = urlparse(receipt["url"])
        assert url.hostname == "external-api.kalshi.com"
        assert url.path.endswith("/markets/" + w["market"] + "/candlesticks")
        assert parse_qs(url.query) == {
            "start_ts": [str(w["start_ts"])],
            "end_ts": [str(w["end_ts"])],
            "period_interval": ["1"],
        }
        raw = CACHE / (receipt["cache_key"] + ".json")
        if digest(raw) != receipt["cache_sha256"]:
            raise ValueError("Quote response checksum mismatch")
        actual = json.loads(raw.read_text())["candlesticks"]
        expected = [
            [
                c["end_period_ts"],
                c.get("yes_bid", {}).get("close_dollars"),
                c.get("yes_ask", {}).get("close_dollars"),
                c.get("volume_fp", "0"),
            ]
            for c in sorted(actual, key=lambda c: c["end_period_ts"])
        ]
        if expected != w["candles"]:
            raise ValueError("Compact quotes differ from provider response")
    signals, samples, _, summary = calculate(p["markets"], qs)
    for s in signals:
        if s["status"] == "eligible":
            assert s["initial_ts"] >= s["decision_ts"] + 120
            assert (
                s["decision_ts"]
                >= max(
                    timestamp(s["previous_available_at"]),
                    timestamp(s["current_available_at"]),
                )
                + 60
            )
    for r in samples:
        assert r["future_ts"] - r["initial_ts"] == r["horizon_minutes"] * 60
        if r["status"] == "observed":
            assert (
                abs(r["ask_change_cents"] - (r["future_ask"] - r["initial_ask"]) * 100)
                < 1e-10
            )
    import contextlib
    import io
    import socket
    from unittest.mock import patch

    paths = [
        DIRECTORY / name
        for name in [
            "signals.csv",
            "samples.csv",
            "exclusions.csv",
            "summary.json",
            "summary.md",
        ]
    ]
    before = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    with (
        patch.object(
            socket.socket,
            "connect",
            side_effect=AssertionError("Network forbidden in replay"),
        ),
        contextlib.redirect_stdout(io.StringIO()),
    ):
        run()
    assert before == {str(path.relative_to(ROOT)): digest(path) for path in paths}
    assert summary == json.loads((DIRECTORY / "summary.json").read_text())
    result = {
        "status": "passed",
        "quote_responses_verified": len(p["windows"]),
        "signals_verified": len(signals),
        "horizon_records_verified": len(samples),
        "network_disabled_replay_identical": True,
        "output_sha256": before,
        "inputs_sha256": digest(DIRECTORY / "inputs.json"),
    }
    (DIRECTORY / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return result
