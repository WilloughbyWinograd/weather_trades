"""Explicit read-only acquisition, research replay, report and verification commands."""

import argparse


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "command",
        choices=[
            "inventory",
            "stations",
            "acquire",
            "forecasts",
            "validate",
            "backtest",
            "replay",
            "report",
            "verify",
            "locations",
            "availability",
            "check-noaa",
            "tweet-prices",
            "replay-tweet-prices",
            "verify-tweet-prices",
            "compare-exits",
            "replay-exits",
            "verify-exits",
            "compare-hrrr-range",
            "replay-hrrr-range",
            "verify-hrrr-range",
        ],
    )
    a = p.parse_args()
    if a.command == "inventory":
        from .inventory import build

        build()
    elif a.command == "stations":
        from .stations import build

        build()
    elif a.command == "acquire":
        from .markets import acquire

        acquire()
    elif a.command == "forecasts":
        from .forecasts import acquire

        acquire()
    elif a.command == "validate":
        from .validation import validate_stations

        validate_stations()
    elif a.command == "backtest":
        from .simulator import run

        run()
    elif a.command == "replay":
        from .simulator import run

        run(offline=True)
    elif a.command == "report":
        from .report import build

        build()
    elif a.command == "verify":
        from .verify import verify

        verify()
    elif a.command == "locations":
        from .location_scan import scan

        scan()
    elif a.command == "availability":
        from .publication import audit

        audit()
    elif a.command == "check-noaa":
        from .noaa_check import run

        run()
    elif a.command == "tweet-prices":
        from .price_response import acquire

        acquire()
    elif a.command == "replay-tweet-prices":
        from .price_response import run

        run()
    elif a.command == "verify-tweet-prices":
        from .price_response import verify

        verify()
    elif a.command == "compare-exits":
        from .exits import acquire

        acquire()
    elif a.command == "replay-exits":
        from .exits import run

        run()
    elif a.command == "verify-exits":
        from .exits import verify

        verify()
    elif a.command == "compare-hrrr-range":
        from .hrrr_range import acquire

        acquire()
    elif a.command == "replay-hrrr-range":
        from .hrrr_range import run

        run()
    elif a.command == "verify-hrrr-range":
        from .hrrr_range import verify

        verify()


if __name__ == "__main__":
    main()
