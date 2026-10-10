"""Compact, versioned inputs for a network-free replay of the published study."""

import hashlib
import json
from .http import ROOT

SNAPSHOT = ROOT / "reports/replay-inputs.json"
BOUND_FILES = [
    "config/strategy.json",
    "config/stations.csv",
    "reports/forecast-samples.csv",
    "reports/station-validation.csv",
    "reports/fee-evidence.json",
]
MARKET_FIELDS = [
    "ticker",
    "event_ticker",
    "series_ticker",
    "target_date",
    "strike_type",
    "floor_strike",
    "cap_strike",
    "expiration_value",
    "result",
    "created_time",
    "open_time",
    "close_time",
    "settlement_ts",
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(markets, series, quotes, signals):
    used_series = {m["series_ticker"] for m in markets}
    decisions = {s["market"]: s["decision_ts"] for s in signals}
    retained = {}
    for ticker, candles in quotes.items():
        selected = []
        for c in candles:
            minute = (c["end_period_ts"] - decisions[ticker]) / 60
            # Exact union (plus harmless intervening minutes) of frozen quote windows.
            if 2 <= minute <= 21 or 62 <= minute <= 67 or 122 <= minute <= 127:
                selected.append(
                    [
                        c["end_period_ts"],
                        c.get("yes_bid", {}).get("close_dollars"),
                        c.get("yes_ask", {}).get("close_dollars"),
                        c.get("yes_ask", {}).get("high_dollars"),
                        c.get("volume_fp", "0"),
                    ]
                )
        retained[ticker] = selected
    payload = {
        "schema_version": 1,
        "bound_files": {p: digest(ROOT / p) for p in BOUND_FILES},
        "market_source_sha256": digest(ROOT / "data/raw/markets.json"),
        "quote_columns": [
            "end_period_ts",
            "yes_bid_close_dollars",
            "yes_ask_close_dollars",
            "yes_ask_high_dollars",
            "volume_fp",
        ],
        "markets": [
            {
                **{k: m[k] for k in MARKET_FIELDS if k in m},
                "rules_sha256": hashlib.sha256(
                    (m["rules_primary"] + "\n" + m["rules_secondary"]).encode()
                ).hexdigest(),
            }
            for m in markets
        ],
        "series": [
            {k: s.get(k) for k in ["ticker", "fee_type", "fee_multiplier"]}
            for s in series
            if s["ticker"] in used_series
        ],
        "quotes": retained,
    }
    SNAPSHOT.write_text(json.dumps(payload, separators=(",", ":")) + "\n")


def load():
    data = json.loads(SNAPSHOT.read_text())
    if data["schema_version"] != 1:
        raise ValueError("Unsupported replay snapshot")
    for name, expected in data["bound_files"].items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"Replay input changed: {name}")
    quotes = {
        ticker: [
            {
                "end_period_ts": t,
                "yes_bid": {"close_dollars": bid},
                "yes_ask": {"close_dollars": ask, "high_dollars": high},
                "volume_fp": volume,
            }
            for t, bid, ask, high, volume in candles
        ]
        for ticker, candles in data["quotes"].items()
    }
    return data["markets"], data["series"], quotes
