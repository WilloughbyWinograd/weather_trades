"""Paired forecast signals and chronological, cash-constrained hypothetical portfolios."""

import csv, json
from collections import defaultdict, Counter
from decimal import Decimal, ROUND_HALF_UP
from .http import ROOT
from .forecasts import settings, days, station_rows
from .history import timestamp, candles, quote
from .fees import units, size, fee
from .markets import write_csv, series


def rows(path):
    return list(csv.DictReader((ROOT / path).open()))


def rounded(v):
    return int(Decimal(str(v)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def contains(m, value):
    kind = m["strike_type"]
    if kind == "less":
        return value < float(m["cap_strike"])
    if kind == "greater":
        return value > float(m["floor_strike"])
    if kind == "between":
        return float(m["floor_strike"]) <= value <= float(m["cap_strike"])
    return False


def signals(day_basis="standard", source=None):
    cfg = settings()
    markets = (
        source[0]
        if source
        else json.loads((ROOT / "data/raw/markets.json").read_text())
    )
    valid = {
        r["event"]: r
        for r in rows("reports/station-validation.csv")
        if r["status"].startswith("verified")
    }
    forecasts = {
        (r["cli"], r["date"], r["model"], int(r["run_hour"])): r
        for r in rows("reports/forecast-samples.csv")
        if r["day_basis"] == day_basis and r["status"] == "complete"
    }
    events = defaultdict(list)
    for m in markets:
        events[m["event_ticker"]].append(m)
    metadata = {s["ticker"]: s for s in (source[1] if source else series())}
    output = []
    accuracy = []
    excluded = []
    for event, ms in sorted(events.items()):
        if event not in valid:
            excluded.append(
                {"event": event, "reason": "station or settlement validation failed"}
            )
            continue
        v = valid[event]
        cli = v["cli"]
        day = v["date"]
        city = v["city"].split(" (")[0]
        obs = float(ms[0]["expiration_value"])
        keys = [
            (cli, day, model, h)
            for model in cfg["models"]
            for h in [cfg["previous_cycle_utc_hour"], cfg["current_cycle_utc_hour"]]
        ]
        if any(k not in forecasts for k in keys):
            excluded.append(
                {"event": event, "reason": "paired complete forecast unavailable"}
            )
            continue
        ms = sorted(ms, key=lambda m: float(m.get("floor_strike", -10000)))
        if (
            len(ms) < 2
            or sum(m["result"] == "yes" for m in ms) != 1
            or any(contains(m, obs) != (m["result"] == "yes") for m in ms)
        ):
            excluded.append(
                {"event": event, "reason": "inconsistent or unsupported outcomes"}
            )
            continue
        for model in cfg["models"]:
            before = forecasts[(cli, day, model, cfg["previous_cycle_utc_hour"])]
            after = forecasts[(cli, day, model, cfg["current_cycle_utc_hour"])]
            previous = float(before["high_f"])
            current = float(after["high_f"])
            revision = (current - previous) / 1.8
            old = [i for i, m in enumerate(ms) if contains(m, rounded(previous))]
            new = [i for i, m in enumerate(ms) if contains(m, rounded(current))]
            accuracy.append(
                {
                    "model": model,
                    "city": city,
                    "station": v["station"],
                    "date": day,
                    "event": event,
                    "run": after["run"],
                    "predicted_high_f": current,
                    "observed_high_f": obs,
                    "error_f": current - obs,
                    "absolute_error_f": abs(current - obs),
                    "correct_outcome": int(
                        len(new) == 1 and ms[new[0]]["result"] == "yes"
                    ),
                    "phase": "evaluation"
                    if day >= cfg["evaluation_start"]
                    else "development",
                }
            )
            if (
                abs(revision) + 1e-10 < cfg["minimum_revision_celsius"]
                or len(old) != 1
                or len(new) != 1
                or old == new
            ):
                continue
            idx = old[0] + (1 if new[0] > old[0] else -1)
            m = ms[idx]
            decision = timestamp(after["run"]) + cfg["release_lag_hours"] * 3600
            if any(
                timestamp(x["created_time"]) > decision
                or timestamp(x["open_time"]) > decision
                for x in ms
            ):
                excluded.append(
                    {
                        "event": event,
                        "model": model,
                        "reason": "outcome definitions not open at signal",
                    }
                )
                continue
            sm = metadata[m["series_ticker"]]
            if sm.get("fee_type") != "quadratic" or sm.get("fee_multiplier") != 1:
                excluded.append(
                    {
                        "event": event,
                        "model": model,
                        "reason": "unsupported fee schedule",
                    }
                )
                continue
            if day < cfg["fee_effective_start"]:
                raise ValueError("Unknown historical fees")
            output.append(
                {
                    "model": model,
                    "city": city,
                    "station": v["station"],
                    "date": day,
                    "event": event,
                    "market": m["ticker"],
                    "run": after["run"],
                    "previous_run": before["run"],
                    "previous_high_f": previous,
                    "current_high_f": current,
                    "revision_c": revision,
                    "decision_ts": decision,
                    "settlement_ts": timestamp(m["settlement_ts"]),
                    "winner": m["result"] == "yes",
                    "phase": "evaluation"
                    if day >= cfg["evaluation_start"]
                    else "development",
                    "market_record": m,
                }
            )
    return output, accuracy, excluded


def prepare(signals):
    bymarket = {}
    for s in signals:
        if s["market"] not in bymarket:
            bymarket[s["market"]] = candles(
                s["market_record"], s["decision_ts"], s["decision_ts"] + 3 * 3600
            )
            print("quotes", s["market"], len(bymarket[s["market"]]), flush=True)
    return bymarket


def replay(
    signals,
    market_candles,
    lag_hours=5,
    delay=1,
    conservative=False,
    fee_rounding="0.0001",
    phase=None,
    unconstrained=False,
    volume_cap=False,
):
    cfg = settings()
    cash = units(cfg["initial_cash_dollars"])
    open_positions = []
    ledger = []
    used = set()
    peak = cash
    maxdd = 0
    turnover = 0
    totalfees = 0
    max_exposure = 0
    pending = []
    events = []

    def mark(ts, kind):
        nonlocal peak, maxdd, max_exposure
        equity = cash + sum(p["cost_units"] for p in open_positions)
        peak = max(peak, equity)
        maxdd = max(maxdd, peak - equity)
        max_exposure = max(max_exposure, sum(p["cost_units"] for p in open_positions))
        events.append(
            {
                "timestamp": ts,
                "kind": kind,
                "cash": cash / 10000,
                "equity_at_cost": equity / 10000,
                "capital_at_cost": sum(p["cost_units"] for p in open_positions) / 10000,
                "open_positions": len(open_positions),
            }
        )

    def settle(until):
        nonlocal cash
        due = sorted(
            [p for p in open_positions if p["settlement_ts"] <= until],
            key=lambda p: (p["settlement_ts"], p["market"]),
        )
        for p in due:
            cash += p["payout_units"]
            open_positions.remove(p)
            mark(p["settlement_ts"], "settlement")

    for s in signals:
        if phase and s["phase"] != phase:
            continue
        q = quote(
            market_candles[s["market"]],
            s["decision_ts"] + (lag_hours - cfg["release_lag_hours"]) * 3600,
            delay,
            conservative,
        )
        base = {k: v for k, v in s.items() if k != "market_record"}
        base["decision_ts"] = (
            s["decision_ts"] + (lag_hours - cfg["release_lag_hours"]) * 3600
        )
        if not q:
            base["status"] = "no later eligible quote"
            ledger.append(base)
            continue
        if (
            not cfg["minimum_price_dollars"]
            <= q["price"]
            <= cfg["maximum_price_dollars"]
        ):
            base.update(q)
            base["status"] = "price outside band"
            ledger.append(base)
            continue
        if q["entry_ts"] >= s["settlement_ts"] or q["entry_ts"] >= timestamp(
            s["market_record"]["close_time"]
        ):
            base["status"] = "market closed before entry"
            ledger.append(base)
            continue
        pending.append({**base, **q})
    for s in sorted(pending, key=lambda x: (x["entry_ts"], x["city"], x["market"])):
        settle(s["entry_ts"])
        key = (s["city"], s["date"])
        if key in used:
            s["status"] = "duplicate city day"
            ledger.append(s)
            continue
        if len(open_positions) >= cfg["maximum_open_positions"] and not unconstrained:
            s["status"] = "position limit"
            ledger.append(s)
            continue
        budget = (
            units(cfg["entry_budget_dollars"])
            if unconstrained
            else min(cash, units(cfg["entry_budget_dollars"]))
        )
        quantity, cost, f = size(budget, s["price"], fee_rounding)
        if volume_cap:
            quantity = min(quantity, int(s["volume"]))
            if not quantity:
                s["status"] = "insufficient observed volume"
                ledger.append(s)
                continue
            cost = quantity * units(s["price"])
            f = fee(quantity, s["price"], fee_rounding)
        if not quantity:
            s["status"] = "insufficient cash"
            ledger.append(s)
            continue
        payout = quantity * 10000 if s["winner"] else 0
        cash -= cost + f
        used.add(key)
        turnover += cost
        totalfees += f
        s.update(
            {
                "status": "filled assumption",
                "quantity": quantity,
                "cost": cost / 10000,
                "fee": f / 10000,
                "payout": payout / 10000,
                "profit": (payout - cost - f) / 10000,
                "cash_after_entry": cash / 10000,
                "cost_units": cost,
                "payout_units": payout,
            }
        )
        if not unconstrained and cash < 0:
            raise AssertionError("Negative available cash")
        open_positions.append(s)
        ledger.append(s)
        mark(s["entry_ts"], "entry")
    settle(float("inf"))
    trades = [s for s in ledger if s["status"] == "filled assumption"]
    profits = sum(s["profit"] for s in trades)
    if abs((cash - units(cfg["initial_cash_dollars"])) / 10000 - profits) > 1e-7:
        raise AssertionError("Ledger does not reconcile")
    duration = (
        events[-1]["timestamp"] - events[0]["timestamp"] if len(events) > 1 else 0
    )
    committed_seconds = sum(
        (b["timestamp"] - a["timestamp"]) * a["capital_at_cost"]
        for a, b in zip(events, events[1:])
    )
    summary = {
        "initial_cash": cfg["initial_cash_dollars"],
        "ending_cash": cash / 10000,
        "net_profit": (cash - units(cfg["initial_cash_dollars"])) / 10000,
        "return_percent": (cash / units(cfg["initial_cash_dollars"]) - 1) * 100,
        "trades": len(trades),
        "wins": sum(t["winner"] for t in trades),
        "win_rate": sum(t["winner"] for t in trades) / len(trades) if trades else None,
        "fees": totalfees / 10000,
        "turnover": turnover / 10000,
        "maximum_drawdown_at_cost": maxdd / 10000,
        "maximum_capital_at_cost": max_exposure / 10000,
        "average_committed_first_entry_to_final_settlement": committed_seconds
        / duration
        if duration
        else 0,
        "rejections": dict(
            Counter(t["status"] for t in ledger if t["status"] != "filled assumption")
        ),
    }
    return summary, ledger, events


def run(offline=False):
    from . import evidence
    from .fees import audit

    cfg = settings()
    forecasts = rows("reports/forecast-samples.csv")
    expected = (
        len(list(days(cfg["study_start"], cfg["study_end"])))
        * len(station_rows())
        * len(cfg["models"])
        * 2
        * 2
    )
    keys = {
        (r["cli"], r["date"], r["model"], r["run_hour"], r["day_basis"])
        for r in forecasts
    }
    if len(forecasts) != expected or len(keys) != expected:
        raise ValueError(
            "Forecast acquisition matrix is incomplete or duplicated; finish acquisition before replay"
        )
    if not offline:
        audit()
    source = evidence.load() if offline else None
    sig, accuracy, excluded = signals(source=source)
    write_csv("reports/accuracy.csv", accuracy)
    write_csv("reports/excluded-events.csv", excluded)
    write_csv(
        "reports/signals.csv",
        [{k: v for k, v in s.items() if k != "market_record"} for s in sig],
    )
    quotes = source[2] if source else prepare(sig)
    result = []
    scenarios = [
        ("baseline", {}),
        ("conservative", {"conservative": True}),
        ("volume_capped", {"conservative": True, "volume_cap": True}),
        ("release_6h", {"lag_hours": 6}),
        ("release_7h", {"lag_hours": 7}),
        ("delay_5m", {"delay": 5}),
        ("delay_15m", {"delay": 15}),
        ("cent_fees", {"fee_rounding": "0.01"}),
        ("development", {"phase": "development"}),
        ("evaluation", {"phase": "evaluation"}),
        ("evaluation_conservative", {"phase": "evaluation", "conservative": True}),
        (
            "evaluation_volume_capped",
            {"phase": "evaluation", "conservative": True, "volume_cap": True},
        ),
        ("unconstrained", {"unconstrained": True}),
    ]
    for model in settings()["models"]:
        selected = [s for s in sig if s["model"] == model]
        for name, kw in scenarios:
            summary, ledger, events = replay(selected, quotes, **kw)
            result.append({"model": model, "scenario": name, **summary})
            write_csv("reports/ledger-" + model + "-" + name + ".csv", ledger)
            write_csv("reports/cash-" + model + "-" + name + ".csv", events)
    civil, _, _ = signals("civil", source=source)
    civilquotes = source[2] if source else prepare(civil)
    for model in settings()["models"]:
        summary, ledger, events = replay(
            [s for s in civil if s["model"] == model], civilquotes
        )
        result.append({"model": model, "scenario": "civil_day", **summary})
        write_csv("reports/ledger-" + model + "-civil_day.csv", ledger)
    if not offline:
        evidence.save(
            json.loads((ROOT / "data/raw/markets.json").read_text()),
            series(),
            {**quotes, **civilquotes},
            sig + civil,
        )
    (ROOT / "reports/results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)
    return result


if __name__ == "__main__":
    run()
