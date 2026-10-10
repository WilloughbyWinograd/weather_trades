"""Candle routing and strictly later quote selection; never infer order-book depth."""

from datetime import datetime
import math
from .http import get, BASE


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def candles(market, start, end):
    cutoff = get(BASE + "/historical/cutoff")
    archived = timestamp(market["settlement_ts"]) < timestamp(
        cutoff["market_settled_ts"]
    )
    suffix = (
        "/historical/markets/" + market["ticker"] + "/candlesticks"
        if archived
        else "/series/"
        + market["series_ticker"]
        + "/markets/"
        + market["ticker"]
        + "/candlesticks"
    )
    data = get(
        BASE + suffix,
        {"start_ts": int(start), "end_ts": int(end), "period_interval": 1},
    )
    return sorted(data["candlesticks"], key=lambda x: x["end_period_ts"])


def quote(candles, decision, delay, conservative=False):
    earliest = decision + delay * 60 + 60
    latest = earliest + 5 * 60
    for c in candles:
        t = c["end_period_ts"]
        if not earliest <= t <= latest:
            continue
        ask = c.get("yes_ask", {}).get(
            "high_dollars" if conservative else "close_dollars"
        )
        bid = c.get("yes_bid", {}).get("close_dollars")
        if ask is None or bid is None:
            continue
        ask = float(ask)
        bid = float(bid)
        if (
            not math.isfinite(ask)
            or not math.isfinite(bid)
            or not 0 <= bid <= ask <= 1
            or ask == 0
        ):
            continue
        if conservative:
            if float(c.get("volume_fp", 0)) <= 0:
                continue
            ask = round(ask + 0.02, 4)
        return {
            "entry_ts": t,
            "price": ask,
            "bid": bid,
            "volume": float(c.get("volume_fp", 0)),
            "quote_end_ts": t,
            "quote_depth": "unknown",
        }
    return None
