"""Exact decimal taker fees; integer 1/10000-dollar account units."""

from decimal import Decimal, ROUND_CEILING
import json

UNIT = Decimal("0.0001")


def units(value):
    return int(Decimal(str(value)) / UNIT)


def fee(quantity, price, rounding="0.0001"):
    p = Decimal(str(price))
    cost = p * quantity
    raw = Decimal("0.07") * quantity * p * (1 - p)
    quantum = Decimal(rounding)
    total = ((cost + raw) / quantum).to_integral_value(rounding=ROUND_CEILING) * quantum
    return units(total - cost)


def size(budget, price, rounding="0.0001"):
    p = units(price)
    if p <= 0:
        return 0, 0, 0
    q = budget // p
    while q and q * p + fee(q, price, rounding) > budget:
        q -= 1
    f = fee(q, price, rounding) if q else 0
    return q, q * p, f


def audit():
    """Fail closed if the fixed study formula conflicts with recorded overrides."""
    from .http import ROOT, BASE, get, pages

    markets = json.loads((ROOT / "data/raw/markets.json").read_text())
    used_series = {m["series_ticker"] for m in markets}
    used_events = {m["event_ticker"] for m in markets}
    series_changes = get(BASE + "/series/fee_changes", {"show_historical": "true"})[
        "series_fee_change_arr"
    ]
    event_changes = list(
        pages("/events/fee_changes", "event_fee_changes", {"limit": 1000})
    )
    relevant = [r for r in series_changes if r["series_ticker"] in used_series] + [
        r for r in event_changes if r["event_ticker"] in used_events
    ]
    evidence = {
        "series_changes_returned": len(series_changes),
        "event_changes_returned": len(event_changes),
        "studied_series": sorted(used_series),
        "relevant_overrides": relevant,
        "fee_formula": "0.07 * contracts * price * (1-price)",
        "schedule_effective_date": "2026-07-07",
        "schedule_url": "https://kalshi.com/docs/kalshi-fee-schedule.pdf",
        "historical_series_source": BASE + "/series/fee_changes?show_historical=true",
        "historical_event_source": BASE + "/events/fee_changes?limit=1000",
        "status": "unsupported overrides"
        if relevant
        else "no studied series or event overrides returned",
    }
    (ROOT / "reports/fee-evidence.json").write_text(
        json.dumps(evidence, indent=2) + "\n"
    )
    if relevant:
        raise ValueError(
            "Historical fee override requires a dated fee adapter before replay"
        )
    if any(m.get("notional_value_dollars") != "1.0000" for m in markets):
        raise ValueError("Unsupported contract payout")
    return evidence
