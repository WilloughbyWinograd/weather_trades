"""One-change HRRR comparison: buy the bracket containing the updated forecast."""

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import json
from urllib.parse import parse_qs, urlparse

from . import exits, price_response
from .evidence import digest
from .history import candles, quote, timestamp
from .http import BASE, CACHE, ROOT, get
from .markets import write_csv

DIRECTORY = ROOT / "reports/hrrr-updated-range"
BOUND_FILES = [
    "config/hrrr-updated-range.json",
    "config/tweet-price-response.json",
    "config/exit-comparison.json",
    "reports/tweet-price-response/inputs.json",
    "reports/tweet-price-response/signals.csv",
    "reports/exit-comparison/ledger.csv",
    "reports/replay-inputs.json",
    "reports/fee-evidence.json",
]
ORIGINAL = "Original one-degree step"
UPDATED = "Updated forecast range"


def candidates(markets):
    signals, _, _ = price_response.make_signals(markets, updated_forecast=True)
    return [s for s in signals if s["model"] == "HRRR"]


def compact(cs):
    return [
        [
            c["end_period_ts"],
            c.get("yes_bid", {}).get("close_dollars"),
            c.get("yes_ask", {}).get("close_dollars"),
            c.get("volume_fp", "0"),
        ]
        for c in cs
    ]


def acquire():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    p, _ = price_response.load()
    original = json.loads((ROOT / "reports/replay-inputs.json").read_text())["markets"]
    by_ticker = {m["ticker"]: m for m in original}
    cfg = price_response.settings()
    minutes = cfg["execution_delay_minutes"] + 1 + cfg["quote_max_wait_minutes"]
    windows = sorted(
        (s["market"], s["decision_ts"], s["decision_ts"] + minutes * 60)
        for s in candidates(p["markets"])
        if s["status"] == "candidate"
    )
    cutoff = get(BASE + "/historical/cutoff")

    def fetch(window):
        ticker, start, end = window
        m = by_ticker[ticker]
        cs = candles(m, start, end)
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
        return {
            "market": ticker,
            "start_ts": start,
            "end_ts": end,
            "source": price_response.source_receipt(BASE + suffix, params),
            "candles": compact(cs),
        }

    records = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        for i, w in enumerate(executor.map(fetch, windows), 1):
            records.append(w)
            if i % 25 == 0:
                print("updated-range quote windows", i, "of", len(windows), flush=True)
    payload = {
        "schema_version": 1,
        "bound_files": {path: digest(ROOT / path) for path in BOUND_FILES},
        "windows": records,
    }
    (DIRECTORY / "inputs.json").write_text(
        json.dumps(payload, separators=(",", ":")) + "\n"
    )
    return run()


def load():
    p = json.loads((DIRECTORY / "inputs.json").read_text())
    if p["schema_version"] != 1 or set(p["bound_files"]) != set(BOUND_FILES):
        raise ValueError("Unsupported HRRR range comparison inputs")
    for name, expected in p["bound_files"].items():
        if digest(ROOT / name) != expected:
            raise ValueError("Changed HRRR comparison input: " + name)
    qs = defaultdict(dict)
    for w in p["windows"]:
        for t, bid, ask, volume in w["candles"]:
            c = {
                "end_period_ts": t,
                "yes_bid": {"close_dollars": bid},
                "yes_ask": {"close_dollars": ask},
                "volume_fp": volume,
            }
            if qs[w["market"]].setdefault(t, c) != c:
                raise ValueError("Conflicting historical quote versions")
    return p, {
        ticker: sorted(cs.values(), key=lambda c: c["end_period_ts"])
        for ticker, cs in qs.items()
    }


def calculate(qs):
    p, baseline_qs = price_response.load()
    cfg = price_response.settings()
    baseline, _, _, _ = price_response.calculate(p["markets"], baseline_qs)
    baseline = [s for s in baseline if s["model"] == "HRRR"]
    signals = candidates(p["markets"])
    for s in signals:
        if s["status"] != "candidate":
            continue
        q = quote(
            qs.get(s["market"], []), s["decision_ts"], cfg["execution_delay_minutes"]
        )
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
    original = json.loads((ROOT / "reports/replay-inputs.json").read_text())["markets"]
    markets = {m["ticker"]: m for m in original}
    ledger = []
    for label, ss in [(ORIGINAL, baseline), (UPDATED, signals)]:
        for s in ss:
            s["rule"] = label
            if s["status"] != "eligible":
                continue
            r = exits.one_exit(
                s,
                {"name": "Settlement", "kind": "settlement"},
                [],
                markets[s["market"]],
                exits.settings(),
            )
            r.update(
                rule=label,
                event=s["event"],
                decision_ts=s["decision_ts"],
                forecast_high_f=s["current_high_c"] * 1.8 + 32,
                target_integer_f=s["target_integer_f"],
                gross_profit=(r["exit_proceeds_units"] - r["entry_cost_units"]) / 10000,
            )
            ledger.append(r)
    event_sets = [
        {r["event"] for r in ledger if r["rule"] == label}
        for label in [ORIGINAL, UPDATED]
    ]
    common = event_sets[0] & event_sets[1]
    for r in ledger:
        r["common_sample"] = r["event"] in common
    results = []
    for phase in ["full", "earlier", "later"]:
        for cohort in ["all eligible", "common city-days"]:
            for label in [ORIGINAL, UPDATED]:
                rs = [
                    r
                    for r in ledger
                    if r["rule"] == label
                    and (phase == "full" or r["phase"] == phase)
                    and (cohort == "all eligible" or r["common_sample"])
                ]
                n = len(rs)
                cost = sum(r["entry_cost_units"] for r in rs) / 10000
                fees = sum(r["entry_fee_units"] for r in rs) / 10000
                payout = sum(r["exit_proceeds_units"] for r in rs) / 10000
                net = sum(r["net_profit_units"] for r in rs) / 10000
                results.append(
                    {
                        "rule": label,
                        "phase": phase,
                        "cohort": cohort,
                        "entries": n,
                        "wins": sum(r["exit_price"] == 1 for r in rs),
                        "cost": cost,
                        "fees": fees,
                        "payout": payout,
                        "gross_profit": payout - cost,
                        "net_profit": net,
                        "mean_net_profit": net / n if n else None,
                        "mean_net_profit_95_percent_date_bootstrap": exits.interval(rs),
                    }
                )
    by_event = {(r["rule"], r["event"]): r for r in ledger}
    differences = [
        {
            "date": by_event[(UPDATED, e)]["date"],
            "net_profit": by_event[(UPDATED, e)]["net_profit"]
            - by_event[(ORIGINAL, e)]["net_profit"],
        }
        for e in sorted(common)
    ]
    summary = {
        "model": "HRRR",
        "study_start": cfg["study_start"],
        "study_end": cfg["study_end"],
        "revision_signals": len(signals),
        "signal_statuses": {
            label: dict(Counter(s["status"] for s in ss))
            for label, ss in [(ORIGINAL, baseline), (UPDATED, signals)]
        },
        "matched_entries": len(common),
        "matched_mean_net_improvement": sum(r["net_profit"] for r in differences)
        / len(differences)
        if differences
        else None,
        "matched_mean_net_improvement_95_percent_date_bootstrap": exits.interval(
            differences
        ),
        "results": results,
    }
    return baseline + signals, ledger, summary


def report(s):
    all_results = [
        r
        for r in s["results"]
        if r["phase"] == "full" and r["cohort"] == "all eligible"
    ]
    net_change = all_results[1]["net_profit"] - all_results[0]["net_profit"]
    direction = "increased" if net_change > 0 else "reduced"
    lines = [
        "# HRRR updated-forecast range",
        "",
        f"Buying the updated forecast range {direction} total net profit by ${abs(net_change):.2f} in this historical sample. The tables also compare the same city-days to account for the changed set of eligible trades.",
        "",
        "One change: buy the contract containing HRRR's updated maximum temperature instead of moving one whole Celsius degree from its previous forecast. All other entry and settlement rules are retained.",
        "",
        "August 28–October 8, 2026. Each paper entry has a maximum budget of 5 dollars including purchase fees. Before-fee profit uses the same contract quantities as the after-fee calculation.",
        "",
        "| Entry rule | Entries | Wins | Before fees | Purchase fees | After fees | Average after fees |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in s["results"]:
        if r["phase"] == "full" and r["cohort"] == "all eligible":
            lines.append(
                f"| {r['rule']} | {r['entries']} | {r['wins']} | ${r['gross_profit']:+.2f} | ${r['fees']:.2f} | ${r['net_profit']:+.2f} | ${r['mean_net_profit']:+.2f} |"
            )
    lines += [
        "",
        "## Same city-days",
        "",
        f"Both rules could trade on {s['matched_entries']} city-days. Contract choice can change quote availability, the entry price, the exact first quoted minute, and eligibility under the unchanged 5–60 cent price band.",
        "",
        "| Entry rule | Before fees | After fees | Average after fees |",
        "| --- | ---: | ---: | ---: |",
    ]
    for r in s["results"]:
        if r["phase"] == "full" and r["cohort"] == "common city-days":
            lines.append(
                f"| {r['rule']} | ${r['gross_profit']:+.2f} | ${r['net_profit']:+.2f} | ${r['mean_net_profit']:+.2f} |"
            )
    low, high = s["matched_mean_net_improvement_95_percent_date_bootstrap"]
    lines += [
        "",
        f"The updated rule changes average net profit by ${s['matched_mean_net_improvement']:+.2f} per matched entry. Its descriptive 95 percent date-cluster bootstrap interval is ${low:+.2f} to ${high:+.2f} (2,000 resamples; fixed seed).",
        "",
        "## Coverage",
        "",
        "| Entry rule | Revision signals | Eligible | No initial quote | Initial ask outside band |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for label, counts in s["signal_statuses"].items():
        lines.append(
            f"| {label} | {sum(counts.values())} | {counts.get('eligible', 0)} | {counts.get('no initial quote', 0)} | {counts.get('initial ask outside band', 0)} |"
        )
    lines += [
        "",
        "## Earlier and later dates",
        "",
        "| Period | Entry rule | Entries | Before fees | After fees |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for r in s["results"]:
        if r["phase"] != "full" and r["cohort"] == "all eligible":
            period = (
                "August 28–September 24"
                if r["phase"] == "earlier"
                else "September 25–October 8"
            )
            lines.append(
                f"| {period} | {r['rule']} | {r['entries']} | ${r['gross_profit']:+.2f} | ${r['net_profit']:+.2f} |"
            )
    lines += [
        "",
        "## Method and evidence",
        "",
        "The revision threshold remains 0.5 degrees Celsius. Updated temperatures convert directly to Fahrenheit and round to the nearest integer, with half away from zero, before selecting the contract range. No whole-Celsius rounding or requirement for a changed range is added. Both rules consume the same original HRRR forecast files and publication markers. Hourly polling, one-minute processing, delayed quote selection, five-minute quote wait, and holding to settlement remain unchanged.",
        "",
        "Decision inputs exclude settlement outcomes. Each rule uses the first valid ask in its entry window and rejects that quote if it is outside the unchanged price band. Missing quotes remain exclusions. There is no selection using the later settlement result. Purchase fees use the existing dated schedule and verified overrides; settlement has no sale fee.",
        "",
        "These dates and some individual outcomes were already examined before proposing this rule. The change was frozen before retrieving its quotes or calculating its aggregate results, but this remains an exploratory comparison on previously studied data. Quoted fills and sufficient capital for every entry are assumed. This is not a cash-constrained portfolio or a live trading result.",
        "",
        "[Frozen change](../../config/hrrr-updated-range.json), [signals and exclusions](signals.csv), [settlement ledger](ledger.csv), [comparison groups](comparison.csv), [complete summary](summary.json), [quote inputs and receipts](inputs.json), and [verification](verification.json). Original [entry rules](../tweet-price-response/summary.md) and [settlement comparison](../exit-comparison/summary.md) remain unchanged.",
        "",
        "Run `python -m weather_trades.cli replay-hrrr-range` for offline reproduction. `compare-hrrr-range` acquires public quotes. `verify-hrrr-range` verifies preserved raw responses, unchanged signal clocks and baseline trades, independent money arithmetic, and an identical replay with network access disabled.",
        "",
    ]
    (DIRECTORY / "summary.md").write_text("\n".join(lines))


def run():
    _, qs = load()
    signals, ledger, summary = calculate(qs)
    write_csv(DIRECTORY / "signals.csv", signals)
    write_csv(DIRECTORY / "ledger.csv", ledger)
    write_csv(DIRECTORY / "comparison.csv", summary["results"])
    (DIRECTORY / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    report(summary)
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def verify():
    p, qs = load()
    entry_inputs, baseline_qs = price_response.load()
    cfg = price_response.settings()
    minutes = cfg["execution_delay_minutes"] + 1 + cfg["quote_max_wait_minutes"]
    expected_windows = sorted(
        (s["market"], s["decision_ts"], s["decision_ts"] + minutes * 60)
        for s in candidates(entry_inputs["markets"])
        if s["status"] == "candidate"
    )
    assert expected_windows == sorted(
        (w["market"], w["start_ts"], w["end_ts"]) for w in p["windows"]
    )
    for w in p["windows"]:
        receipt = w["source"]
        raw = CACHE / (receipt["cache_key"] + ".json")
        assert digest(raw) == receipt["cache_sha256"] == receipt["sha256"]
        url = urlparse(receipt["url"])
        assert url.hostname == "external-api.kalshi.com" and url.path.endswith(
            "/markets/" + w["market"] + "/candlesticks"
        )
        assert parse_qs(url.query) == {
            "start_ts": [str(w["start_ts"])],
            "end_ts": [str(w["end_ts"])],
            "period_interval": ["1"],
        }
        actual = sorted(
            json.loads(raw.read_text())["candlesticks"],
            key=lambda c: c["end_period_ts"],
        )
        assert compact(actual) == w["candles"]
        # A changed contract is the experiment; changed provider history is not.
        original_windows = [
            old
            for old in entry_inputs["windows"]
            if old["market"] == w["market"]
            and old["start_ts"] <= w["start_ts"]
            and old["end_ts"] >= w["end_ts"]
        ]
        if original_windows:
            preserved = [
                c
                for c in baseline_qs.get(w["market"], [])
                if w["start_ts"] <= c["end_period_ts"] <= w["end_ts"]
            ]
            assert compact(preserved) == w["candles"]
    signals, ledger, summary = calculate(qs)
    baseline = {s["event"]: s for s in signals if s["rule"] == ORIGINAL}
    by_ticker = {
        m["ticker"]: m
        for m in json.loads((ROOT / "reports/replay-inputs.json").read_text())[
            "markets"
        ]
    }
    for s in signals:
        if s["rule"] != UPDATED:
            continue
        original = baseline[s["event"]]
        changed = {
            "rule",
            "target_c",
            "target_integer_f",
            "market",
            "close_ts",
            "status",
            "initial_ts",
            "initial_ask",
            "initial_bid",
            "initial_volume",
        }
        assert {k: v for k, v in s.items() if k not in changed} == {
            k: v for k, v in original.items() if k not in changed
        }
        integer = int(
            (Decimal(str(s["current_high_c"])) * Decimal("1.8") + 32).to_integral_value(
                rounding=ROUND_HALF_UP
            )
        )
        assert s["target_integer_f"] == integer
        if "market" in s:
            m = by_ticker[s["market"]]
            if m["strike_type"] == "between":
                assert m["floor_strike"] <= integer <= m["cap_strike"]
            elif m["strike_type"] == "less":
                assert integer < m["cap_strike"]
            elif m["strike_type"] == "greater":
                assert integer > m["floor_strike"]
            else:
                raise AssertionError("Unsupported contract range")
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
    with (ROOT / "reports/exit-comparison/ledger.csv").open() as source:
        old = [
            r
            for r in csv.DictReader(source)
            if r["model"] == "HRRR" and r["policy"] == "Settlement"
        ]
    key = lambda r: (
        r["market"],
        float(r["initial_ts"]),
        float(r["initial_ask"]),
        int(r["quantity"]),
        int(r["entry_cost_units"]),
        int(r["entry_fee_units"]),
        int(r["exit_proceeds_units"]),
        int(r["net_profit_units"]),
    )
    assert sorted(map(key, old)) == sorted(
        map(key, (r for r in ledger if r["rule"] == ORIGINAL))
    )
    for r in ledger:
        price, count = Decimal(str(r["initial_ask"])), r["quantity"]
        independent_fee = (Decimal("0.07") * count * price * (1 - price)).quantize(
            Decimal("0.0001"), rounding=ROUND_CEILING
        )
        payout = Decimal(count if by_ticker[r["market"]]["result"] == "yes" else 0)
        assert float(count * price + independent_fee) == r["entry_outlay"] <= 5
        assert (
            abs(float(payout - count * price - independent_fee) - r["net_profit"])
            < 1e-8
        )
        assert r["exit_ts"] > r["initial_ts"]
    import contextlib
    import io
    import socket
    from unittest.mock import patch

    paths = [
        DIRECTORY / f
        for f in [
            "signals.csv",
            "ledger.csv",
            "comparison.csv",
            "summary.json",
            "summary.md",
        ]
    ]
    before = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    with (
        patch.object(
            socket.socket, "connect", side_effect=AssertionError("Network forbidden")
        ),
        contextlib.redirect_stdout(io.StringIO()),
    ):
        run()
    assert before == {str(path.relative_to(ROOT)): digest(path) for path in paths}
    assert summary == json.loads((DIRECTORY / "summary.json").read_text())
    result = {
        "status": "passed",
        "raw_quote_windows_verified": len(p["windows"]),
        "unchanged_revision_signals": len(baseline),
        "unchanged_baseline_entries": len(old),
        "settlement_records_verified": len(ledger),
        "independent_target_rounding_and_profit_arithmetic": True,
        "network_disabled_replay_identical": True,
        "inputs_sha256": digest(DIRECTORY / "inputs.json"),
        "output_sha256": before,
    }
    (DIRECTORY / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return result
