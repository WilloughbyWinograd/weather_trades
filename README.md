# weather_trades

Compare Global Forecast System (GFS) and High-Resolution Rapid Refresh (HRRR) forecasts for simulated Kalshi daily-high temperature trades.

[Read the performance report](reports/summary.md), [city coverage](reports/coverage.csv), and [methodology](docs/methodology.md).

Each model receives a separate hypothetical **$100**, shared across all eligible cities. The initial study covers August 28–October 8, 2026. September 25–October 8 is the original reserved evaluation period. This correction reuses those dates; it is not a new untouched evaluation. Trading parameters remain frozen.

The program uses actual settlement-station coordinates, individual archived model runs, later bid and ask candles, dated contract outcomes, fees, and cash constraints. Results assume fills because historical executable quantities are unavailable. Missing source runs remain explicit gaps.

**Every consumed forecast file has publication evidence before its simulated trade.** The program reads original public run files directly. Each model's completion marker determines its decision time, followed by polling, processing, and execution delays. Missing or inconsistent evidence stops the calculation or excludes the missing run. Historical executable fills remain unverified.

## Reproduce the published result

Use Python 3.12 or later. Install the locked dependencies in a local environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m weather_trades.cli replay
```

The replay reads compact inputs committed with the report. It makes no network requests and needs no account or credentials. Input checksums prevent silently replaying a changed strategy or forecast table against the saved quotes. Compare `reports/results.json` and the ledger files with their committed versions.

## Reacquire public sources

The commands below populate the ignored source cache and rebuild the study. Public services can revise data or remove older records. The saved replay inputs preserve the published calculation independently.

```sh
.venv/bin/python -m weather_trades.cli inventory
.venv/bin/python -m weather_trades.cli locations
.venv/bin/python -m weather_trades.cli inventory
.venv/bin/python -m weather_trades.cli acquire
.venv/bin/python -m weather_trades.cli stations
.venv/bin/python -m weather_trades.cli forecasts
.venv/bin/python -m weather_trades.cli check-noaa
.venv/bin/python -m weather_trades.cli validate
.venv/bin/python -m weather_trades.cli backtest
.venv/bin/python -m weather_trades.cli report
.venv/bin/python -m weather_trades.cli verify
```

`verify` re-decodes preserved forecast bytes and audits publication evidence, native NOAA samples, station mappings, fees, payouts, and chronological cash. It requires the locally acquired source cache. It does not use synthetic performance data.

Requests are cached and paced. Forecast acquisition uses four workers and bounded byte ranges from public files. It does not consume the forecast API's request allowance. Reuse the cache when resuming. Open-Meteo documents three months of public run-file retention; compact replay inputs remain usable after source expiration.

## Results and evidence

- `reports/summary.md`: evaluation, full-period performance, sensitivity cases, and every included city.
- `reports/coverage.csv`: every discovered city or named resort, including excluded locations and coordinate status.
- `config/stations.csv`: settlement identifiers and sourced station coordinates.
- `reports/forecast-samples.csv`: individual runs, complete-day reductions, and source gaps.
- `reports/source-availability.csv`: availability and forecast-lead coverage by station and model.
- `reports/archive-runs.json`: exact object identities, completion markers, and preserved byte-range checksums.
- `reports/forecast-timing.csv`: publication evidence for all 168 requested runs.
- `reports/noaa-source-checks.json`: 288 comparisons with native NOAA temperature fields.
- `reports/legacy-delay-assumptions/`: superseded fixed-delay scenarios, retained for traceability.
- `reports/publication-probes.json`: the earlier diagnostic that invalidated the five-hour assumption; it is not used for corrected trades.
- `reports/accuracy*.csv` and `reports/by-city.csv`: forecast errors and city contributions.
- `reports/ledger-*.csv` and `reports/cash-*.csv`: accepted signals, rejected entries, and cash events.
- `reports/fee-evidence.json`: fee schedule and historical override audit.
- `reports/source-manifest.csv`: public request URLs, retrieval times, and source checksums.
- `reports/replay-inputs.json`: compact contract metadata and the exact quote windows needed for offline replay.
- `reports/verification.json`: source and ledger verification result.
- `reports/replay-verification.json`: identical offline replay outputs and rejected invalid-evidence cases.

The [implementation plan](docs/implementation-plan.md) also describes extensions beyond this initial study, including earlier history and native model update schedules.

## Spending and execution

This project is personal hypothetical research. Do not place real orders, deposit money, purchase data, or create paid infrastructure. Do not add trading credentials or order-submission code. All external requests are read-only.

Forecast attribution: Open-Meteo, NOAA GFS, and NOAA HRRR. Open-Meteo data is provided under [CC BY 4.0](https://open-meteo.com/en/licence). Market data comes from Kalshi. Settlement observations come from The Weather Company; station coordinates come from NOAA.
