"""Compare predeclared selling rules on identical historical tweet-method entries."""

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from decimal import Decimal, ROUND_CEILING
import json
import random
import statistics
from urllib.parse import parse_qs, urlparse

from . import price_response
from .evidence import digest
from .fees import fee, size, units
from .history import candles, timestamp
from .http import BASE, CACHE, ROOT, get
from .markets import write_csv

DIRECTORY = ROOT / "reports/exit-comparison"
CONFIG = "config/exit-comparison.json"
BOUND_FILES = [
    CONFIG,
    "reports/tweet-price-response/inputs.json",
    "reports/tweet-price-response/signals.csv",
    "reports/fee-evidence.json",
    "reports/replay-inputs.json",
]


def settings():
    return json.loads((ROOT / CONFIG).read_text())


def entries():
    p, qs = price_response.load()
    signals, _, _, _ = price_response.calculate(p["markets"], qs)
    return [s for s in signals if s["status"] == "eligible"]


def acquire():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    cfg = settings()
    original = json.loads((ROOT / "reports/replay-inputs.json").read_text())["markets"]
    markets = {m["ticker"]: m for m in original}
    end_minutes = cfg["trigger_time_cap_minutes"] + cfg["quote_wait_minutes"] + 1
    windows = sorted(
        {
            (s["market"], s["initial_ts"], s["initial_ts"] + end_minutes * 60)
            for s in entries()
        }
    )
    cutoff = get(BASE + "/historical/cutoff")

    def fetch(window):
        ticker, start, end = window
        m = markets[ticker]
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
        return {
            "market": ticker,
            "start_ts": start,
            "end_ts": end,
            "source": price_response.source_receipt(BASE + suffix, params),
            "candles": [
                [
                    c["end_period_ts"],
                    c.get("yes_bid", {}).get("close_dollars"),
                    c.get("yes_ask", {}).get("close_dollars"),
                    c.get("volume_fp", "0"),
                ]
                for c in data
            ],
        }

    records = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        for i, result in enumerate(executor.map(fetch, windows), 1):
            records.append(result)
            if i % 25 == 0:
                print("exit quote windows", i, "of", len(windows), flush=True)
    payload = {
        "schema_version": 1,
        "bound_files": {p: digest(ROOT / p) for p in BOUND_FILES},
        "quote_columns": [
            "end_period_ts",
            "yes_bid_close_dollars",
            "yes_ask_close_dollars",
            "volume_fp",
        ],
        "windows": records,
    }
    (DIRECTORY / "inputs.json").write_text(
        json.dumps(payload, separators=(",", ":")) + "\n"
    )
    return run()


def load():
    p = json.loads((DIRECTORY / "inputs.json").read_text())
    if p["schema_version"] != 1 or set(p["bound_files"]) != set(BOUND_FILES):
        raise ValueError("Unsupported exit comparison inputs")
    for path, expected in p["bound_files"].items():
        if digest(ROOT / path) != expected:
            raise ValueError("Changed exit input: " + path)
    qs = defaultdict(dict)
    for w in p["windows"]:
        for c in w["candles"]:
            if qs[w["market"]].setdefault(c[0], c) != c:
                raise ValueError("Conflicting provider quote versions")
    return p, {m: sorted(v.values()) for m, v in qs.items()}


def valid(c):
    return c[1] is not None and c[2] is not None and 0 < float(c[1]) <= float(c[2]) <= 1


def sell_quote(cs, intended, close, wait):
    return next(
        (
            c
            for c in cs
            if intended <= c[0] <= intended + wait * 60 and c[0] < close and valid(c)
        ),
        None,
    )


def one_exit(s, policy, cs, market, cfg):
    quantity, cost, entry_fee = size(
        units(cfg["entry_budget_dollars"]),
        s["initial_ask"],
        cfg["fee_rounding_dollars"],
    )
    if quantity <= 0:
        raise ValueError("Eligible entry cannot fit paper trade budget")
    r = {
        "model": s["model"],
        "city": s["city"],
        "date": s["date"],
        "market": s["market"],
        "policy": policy["name"],
        "initial_ts": s["initial_ts"],
        "initial_ask": s["initial_ask"],
        "initial_bid": s["initial_bid"],
        "quantity": quantity,
        "entry_cost_units": cost,
        "entry_fee_units": entry_fee,
        "entry_outlay": (cost + entry_fee) / 10000,
        "status": "unresolved exit",
        "phase": "earlier" if s["date"] <= cfg["selection_end"] else "later",
    }
    if policy["kind"] == "settlement":
        if market["result"] not in {"yes", "no"}:
            raise ValueError("Missing verified settlement")
        price = 1 if market["result"] == "yes" else 0
        actual = timestamp(market["settlement_ts"])
        exit_fee = 0
        r.update(exit_reason="settlement", intended_ts=actual)
    else:
        if policy["kind"] == "timed":
            intended = s["initial_ts"] + policy["minutes"] * 60
            reason = "time limit"
        else:
            intended = s["initial_ts"] + cfg["trigger_time_cap_minutes"] * 60
            reason = "six-hour time limit"
            for c in cs:
                if not s["initial_ts"] < c[0] < intended or not valid(c):
                    continue
                movement = (Decimal(c[1]) - Decimal(str(s["initial_ask"]))) * 100
                if (
                    movement >= policy["target_cents"]
                    or movement <= -policy["stop_cents"]
                ):
                    reason = (
                        "profit target"
                        if movement >= policy["target_cents"]
                        else "stop loss"
                    )
                    r.update(trigger_ts=c[0], trigger_bid=float(c[1]))
                    intended = c[0] + cfg["trigger_execution_delay_seconds"]
                    break
        r.update(exit_reason=reason, intended_ts=intended)
        q = sell_quote(
            cs, intended, timestamp(market["close_time"]), cfg["quote_wait_minutes"]
        )
        if q is None:
            return r
        actual, bid, _, volume = q
        price = float(bid)
        exit_fee = fee(quantity, price, cfg["fee_rounding_dollars"])
        r.update(
            exit_quote_volume=float(volume), quote_wait_minutes=(actual - intended) / 60
        )
    proceeds = quantity * units(price)
    profit = proceeds - exit_fee - cost - entry_fee
    r.update(
        status="priced assumption",
        exit_ts=actual,
        exit_price=price,
        exit_proceeds_units=proceeds,
        exit_fee_units=exit_fee,
        net_profit_units=profit,
        net_profit=profit / 10000,
        net_return_percent=100 * profit / (cost + entry_fee),
        holding_minutes=(actual - s["initial_ts"]) / 60,
        net_cents_per_contract=profit / (100 * quantity),
    )
    return r


def interval(records):
    dates = defaultdict(list)
    for r in records:
        dates[r["date"]].append(r["net_profit"])
    groups = list(dates.values())
    if len(groups) < 2:
        return [None, None]
    rng = random.Random(20261010)
    sampled = []
    for _ in range(2000):
        selected = [groups[rng.randrange(len(groups))] for _ in groups]
        sampled.append(sum(map(sum, selected)) / sum(map(len, selected)))
    sampled.sort()
    return [sampled[49], sampled[1949]]


def summarize(ledger, model, policy, phase, cohort):
    rows = [
        r
        for r in ledger
        if r["model"] == model
        and r["policy"] == policy
        and (phase == "full" or r["phase"] == phase)
    ]
    observed = [
        r
        for r in rows
        if r["status"] == "priced assumption"
        and (cohort == "all observed" or r["common_sample"])
    ]
    n = len(observed)
    return {
        "model": model,
        "policy": policy,
        "phase": phase,
        "cohort": cohort,
        "eligible_entries": len(rows),
        "priced_entries": n,
        "unresolved_exits": sum(r["status"] != "priced assumption" for r in rows),
        "mean_net_profit": statistics.mean(r["net_profit"] for r in observed)
        if n
        else None,
        "mean_net_profit_95_percent_date_bootstrap": interval(observed),
        "total_net_profit": sum(r["net_profit_units"] for r in observed) / 10000,
        "return_on_outlay_percent": 100
        * sum(r["net_profit_units"] for r in observed)
        / sum(r["entry_cost_units"] + r["entry_fee_units"] for r in observed)
        if n
        else None,
        "mean_net_cents_per_contract": statistics.mean(
            r["net_cents_per_contract"] for r in observed
        )
        if n
        else None,
        "median_net_profit": statistics.median(r["net_profit"] for r in observed)
        if n
        else None,
        "profitable_entries": sum(r["net_profit_units"] > 0 for r in observed),
        "mean_holding_minutes": statistics.mean(r["holding_minutes"] for r in observed)
        if n
        else None,
        "exit_reasons": dict(Counter(r["exit_reason"] for r in observed)),
    }


def calculate(signals, qs):
    cfg = settings()
    evidence = json.loads((ROOT / "reports/fee-evidence.json").read_text())
    if (
        evidence["relevant_overrides"]
        or evidence["schedule_effective_date"] > cfg["study_start"]
    ):
        raise ValueError("Unresolved fee schedule")
    markets = {
        m["ticker"]: m
        for m in json.loads((ROOT / "reports/replay-inputs.json").read_text())[
            "markets"
        ]
    }
    ledger = [
        one_exit(s, policy, qs.get(s["market"], []), markets[s["market"]], cfg)
        for s in signals
        for policy in cfg["policies"]
    ]
    by_entry = defaultdict(list)
    for r in ledger:
        by_entry[(r["model"], r["market"], r["initial_ts"])].append(r)
    for rs in by_entry.values():
        common = len(rs) == len(cfg["policies"]) and all(
            r["status"] == "priced assumption" for r in rs
        )
        for r in rs:
            r["common_sample"] = common
    summaries = [
        summarize(ledger, model, policy["name"], phase, cohort)
        for model in cfg["models"]
        for policy in cfg["policies"]
        for phase in ["full", "earlier", "later"]
        for cohort in ["common", "all observed"]
    ]
    choices = []
    for model in cfg["models"]:
        options = [
            r
            for r in summaries
            if r["model"] == model
            and r["phase"] == "earlier"
            and r["cohort"] == "common"
            and r["mean_net_profit"] is not None
        ]
        if options:
            best = max(options, key=lambda r: r["mean_net_profit"])
            later = next(
                r
                for r in summaries
                if r["model"] == model
                and r["phase"] == "later"
                and r["cohort"] == "common"
                and r["policy"] == best["policy"]
            )
            choices.append(
                {
                    "model": model,
                    "selected_on_earlier_dates": best["policy"],
                    "earlier": best,
                    "later": later,
                }
            )
    return ledger, {"results": summaries, "earlier_selected_policies": choices}


def run():
    _, qs = load()
    ledger, summary = calculate(entries(), qs)
    write_csv(DIRECTORY / "ledger.csv", ledger)
    write_csv(DIRECTORY / "comparison.csv", summary["results"])
    (DIRECTORY / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    from .exit_report import build

    build(summary, settings(), DIRECTORY)
    print(json.dumps(summary["earlier_selected_policies"], indent=2), flush=True)
    return summary


def verify():
    """Check real-source retention, chronological exits and an independent money calculation."""
    p, qs = load()
    for w in p["windows"]:
        receipt = w["source"]
        raw = CACHE / (receipt["cache_key"] + ".json")
        if digest(raw) != receipt["cache_sha256"]:
            raise ValueError("Source response changed")
        url = urlparse(receipt["url"])
        assert url.hostname == "external-api.kalshi.com" and url.path.endswith(
            "/markets/" + w["market"] + "/candlesticks"
        )
        assert parse_qs(url.query) == {
            "start_ts": [str(w["start_ts"])],
            "end_ts": [str(w["end_ts"])],
            "period_interval": ["1"],
        }
        actual = json.loads(raw.read_text())["candlesticks"]
        compact = [
            [
                c["end_period_ts"],
                c.get("yes_bid", {}).get("close_dollars"),
                c.get("yes_ask", {}).get("close_dollars"),
                c.get("volume_fp", "0"),
            ]
            for c in sorted(actual, key=lambda c: c["end_period_ts"])
        ]
        assert compact == w["candles"]
    signals = entries()
    with (ROOT / settings()["entry_source"]).open() as source:
        published = [r for r in csv.DictReader(source) if r["status"] == "eligible"]
    key = lambda r: (
        r["model"],
        r["market"],
        float(r["initial_ts"]),
        float(r["initial_ask"]),
        float(r["initial_bid"]),
    )
    assert sorted(map(key, signals)) == sorted(map(key, published))
    for s in signals:
        initial = [c for c in qs[s["market"]] if c[0] == s["initial_ts"]]
        assert len(initial) == 1
        assert (
            float(initial[0][1]) == s["initial_bid"]
            and float(initial[0][2]) == s["initial_ask"]
        )
    ledger, summary = calculate(signals, qs)
    cfg = settings()
    for r in ledger:
        if r["status"] != "priced assumption":
            continue
        assert (
            r["exit_ts"] > r["initial_ts"]
            and r["entry_outlay"] <= cfg["entry_budget_dollars"]
        )
        buy, sell, count = (
            Decimal(str(r["initial_ask"])),
            Decimal(str(r["exit_price"])),
            r["quantity"],
        )

        def independent_fee(price):
            amount = Decimal("0.07") * count * price * (1 - price)
            return (amount * 10000).to_integral_value(rounding=ROUND_CEILING) / 10000

        actual_profit = count * (sell - buy) - independent_fee(buy)
        if r["exit_reason"] != "settlement":
            actual_profit -= independent_fee(sell)
            assert (
                r["intended_ts"]
                <= r["exit_ts"]
                <= r["intended_ts"] + cfg["quote_wait_minutes"] * 60
            )
            if "trigger_ts" in r:
                assert (
                    r["exit_ts"]
                    >= r["trigger_ts"] + cfg["trigger_execution_delay_seconds"]
                )
        assert abs(float(actual_profit) - r["net_profit"]) < 1e-8
    import contextlib
    import io
    import socket
    from unittest.mock import patch

    files = [
        DIRECTORY / name
        for name in ["ledger.csv", "comparison.csv", "summary.json", "summary.md"]
    ]
    before = {str(path.relative_to(ROOT)): digest(path) for path in files}
    with (
        patch.object(
            socket.socket, "connect", side_effect=AssertionError("Network forbidden")
        ),
        contextlib.redirect_stdout(io.StringIO()),
    ):
        run()
    assert before == {str(path.relative_to(ROOT)): digest(path) for path in files}
    assert summary == json.loads((DIRECTORY / "summary.json").read_text())
    result = {
        "status": "passed",
        "raw_quote_windows_verified": len(p["windows"]),
        "unchanged_entries": len(signals),
        "policy_records_verified": len(ledger),
        "independent_fee_and_profit_reconciliation": True,
        "network_disabled_replay_identical": True,
        "inputs_sha256": digest(DIRECTORY / "inputs.json"),
        "output_sha256": before,
    }
    (DIRECTORY / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return result
