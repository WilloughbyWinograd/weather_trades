# GFS versus HRRR Kalshi backtest implementation plan

**Goal:** Compare forecast accuracy and simulated trading results across every city represented in Kalshi's available weather-market data.

**Architecture:** A read-only Python pipeline joins market histories, versioned settlement stations, and archived forecast runs. A chronological simulator evaluates both models under identical rules. Compact reports retain every city, including cities with missing data or no HRRR coverage.

**Technology:** Python, HTTP requests, SQLite, and compact tabular exports. Use existing scientific readers only when raw forecast files are necessary. Pin dependencies during implementation.

**Status:** Plan only. Repository creation and documentation publication are complete deliverables for this stage. Acquisition, strategy implementation, and backtesting remain future work.

## 1. Settled decisions

- Repository: private `WilloughbyWinograd/weather_trades`.
- No real money, deposits, orders, paid data, new paid infrastructure, or billable automation.
- Use public read-only interfaces. Do not store trading credentials or implement order placement.
- Use actual settlement station coordinates. City centers and the nearest convenient airport are not substitutes.
- Include every discovered weather-market city in the coverage ledger. Do not select cities by profitability or convenience.
- Compare daily maximum-temperature contracts first, because the proposed strategy concerns tomorrow's high.
- Inventory minimum-temperature, hourly, weekly, rainfall, and other weather contracts too. Identify cities represented only by these products.
- Report those other products as outside the initial strategy, not as absent cities or failed forecasts.
- Keep historical aliases, retired series, contract-rule changes, and station changes.
- Use the longest verified common history per city and station, subject to free access and existing resource limits.
- Separate the paired model comparison from each model's complete available sample.
- Do not write unit tests unless explicitly requested. Use a small, repeatable end-to-end verification with real source records.

## 2. Evidence already checked

These observations establish feasibility, not complete coverage:

- Kalshi public requests succeeded without authentication for historical cutoffs, settled markets, and historical minute candles.
- A historical New York temperature contract returned 388 minute candles. This is not a completeness claim for its trading period.
- The climate and weather series query returned 422 series. This is a series count, not a city count.
- The catalog includes Amsterdam, Beijing, and Geneva temperature series, alongside US cities and multiple aliases.
- Sample historical New York rules name the National Weather Service daily climatological report.
- A more recent New York contract names The Weather Company. Settlement sources must therefore be resolved for each contract version.

The initial probe used the public Kalshi API at `https://external-api.kalshi.com/trade-api/v2`.

## 3. Discover all cities and contracts

Create `src/weather_trades/markets.py` and `config/market-classification.csv`.

1. Fetch the full series catalog, including an unfiltered catalog cross-check.
2. Discover weather series through categories, tags, titles, and contract rules.
3. Read events, recent markets, and archived markets. Follow every cursor until exhaustion.
4. Read `/historical/cutoff` before routing requests between live and historical endpoints.
5. Deduplicate by market identifier. Preserve original series and event identifiers.
6. Classify each contract by weather variable, time interval, location, and settlement method.
7. Resolve aliases to cities without merging distinct stations or contract definitions.
8. Extract city-specific components from multi-city products. Flag unresolved components for review.
9. Record non-city products, such as global temperature averages, separately.
10. Reconcile discovered series and market counts with retrieved records. Never infer completeness from one page.

Produce `reports/coverage.csv` with a row for every discovered city and station association. Include discovery source, series aliases, product classes, historical dates, and eligibility status.

Statuses must distinguish: eligible, no daily-high contract, outside HRRR domain, station unresolved, forecast missing, market history missing, and access blocked.

**Acceptance:** Every weather series has a documented classification. Every city has a coverage row. Unsupported cities remain visible.

## 4. Resolve settlement stations and coordinates

Create `src/weather_trades/stations.py` and `config/stations.csv`.

Read the exact rules and linked settlement source for each market. Resolve the named station using authoritative station metadata. Prefer the station operator, National Weather Service, or National Centers for Environmental Information.

Required fields:

- Canonical city and original market location name.
- Series, market, and rule-version identifiers.
- Settlement provider and source URL.
- Station name and applicable identifiers, such as ICAO, WBAN, or WMO.
- Latitude, longitude, elevation, coordinate datum, and coordinate source URL.
- Coordinate retrieval date and station metadata validity interval.
- Local timezone and the exact settlement-day definition.
- Units, outcome bounds, rounding rules, and source revision policy.
- Verification status and reason for unresolved mappings.

Some settlement locations are not airports. Do not assume an airport from the city name. A station relocation creates a new validity interval. A changed provider requires a new rule mapping even if the city label remains unchanged.

Use the station's latitude and longitude for forecast extraction. Record the selected model grid coordinates and grid elevation separately. Declare one extraction method per model and preserve it throughout the evaluation.

**Acceptance:** Every eligible contract maps to a sourced station and correct historical rule version. Unresolved contracts cannot enter a backtest.

## 5. Establish free historical forecast access

Create `src/weather_trades/forecasts.py` and `reports/source-availability.csv`.

Probe archived individual GFS and HRRR runs before bulk retrieval. Open-Meteo's single-run interface is a candidate, not assumed complete or free for every use. Verify model history, access terms, limits, and whether model selection preserves individual runs.

If necessary, probe free NOAA public archives. Retrieve only needed temperature fields and forecast leads. Do not run either weather model. Do not download entire domains when a bounded subset or reusable field extraction is sufficient.

For each source, record initialization time, forecast lead, valid time, provider availability evidence, retrieval time, model version, and checksum.

Never substitute observations, reanalysis, a stitched best-available forecast, or a later model run for the forecast available at a historical decision time.

HRRR over the contiguous United States normally extends 18 hours from hourly cycles. The 00, 06, 12, and 18 UTC cycles extend 48 hours. Handle Alaska separately according to its actual product schedule. Confirm the historical schedule and domain for each period.

Daily-high comparisons require complete coverage of the contract's target day. Missing afternoon leads are not evidence of a lower maximum. Do not fill short HRRR runs with GFS values.

Start with index requests and a small real-data probe. Estimate storage, requests, and runtime before expanding within the existing resource budget. If free data is unavailable, report the affected dates and cities.

**Acceptance:** Each eligible station has a dated availability manifest. Every forecast value retains run and valid-time provenance.

## 6. Retrieve market history

Create `src/weather_trades/history.py`.

Acquire contract definitions, outcomes, settlement times, minute bid and ask candles, trade history, and historical fee schedules where available. Reconcile live and archived endpoint boundaries.

Record the difference between missing candles, no trades, stale quotes, and valid zero-valued prices. Do not forward-fill prices indefinitely.

Minute candles do not contain a complete historical order book. Trade volume does not prove that our simulated order could have filled. Record available quote depth separately and leave unknown depth unknown.

**Acceptance:** Each market has a coverage interval, gap report, rule snapshot, and settlement outcome. A sample can be traced to the original response.

## 7. Freeze the comparison protocol

Create `config/strategy.json` and `docs/methodology.md` before inspecting profitability.

### Paired comparison

Use identical stations, contracts, target dates, and decision times. At each decision time, choose the latest available complete forecast for each model. Do not select a run by initialization time alone.

Require a preceding eligible forecast from the same model for the same target day. A model switch cannot trigger a revision signal.

Use a common decision schedule anchored to newly available long-range cycles for the primary comparison. Separately evaluate each model at its native update schedule. Report sample-size differences and forecast age.

### Baseline signal

The original post is incomplete. Use these explicit research assumptions:

- Evaluate tomorrow's daily-high contracts, using each contract's local day definition.
- A same-model forecast revision of at least 0.5 degrees Celsius triggers evaluation.
- Convert forecasts to contract units before selecting an outcome. Preserve the threshold's physical meaning across unit systems.
- Identify the outcome containing the previous predicted high under the contract's rounding rules.
- Select the immediately adjacent outcome in the direction of the new predicted high, only if this moves toward its outcome.
- Require that the predicted high changes outcome. Skip ambiguous or overlapping outcome mappings.
- Require a YES purchase price between 5 and 60 cents, inclusive.
- Permit one position per city and target day in each model's portfolio. Do not repeatedly buy on the same update.
- Hold to settlement for the primary experiment. A price-adjustment exit is a separate, predeclared experiment.

This is a reproducible interpretation of the post, not a claim to reproduce its unknown bot exactly.

### Capital and timing

Use separate hypothetical $50 portfolios for GFS and HRRR. Limit each entry to $5 including fees, with at most five open positions. Respect contract quantity increments and minimum orders. Keep funds locked until the simulated exit or settlement.

Process signals chronologically. Break identical-time ties by canonical city identifier, not by eventual returns. Report unfilled signals and capital-blocked signals.

Also calculate unconstrained per-signal results. This separates model quality from the small portfolio's allocation constraint.

Use provider publication evidence when available. Where it is absent, apply a documented conservative release-lag assumption and show sensitivity to longer delays. Label these results as timing-assumed.

For minute candles, enter using a quote from a later completed interval after the signal and declared delay. Never select the candle low using hindsight. Report a quoted-price scenario separately from a conservative fill scenario. Do not claim a validated fill when historical depth is unavailable.

## 8. Build the chronological simulator

Create `src/weather_trades/simulator.py`, `src/weather_trades/fees.py`, and `src/weather_trades/cli.py`.

The engine must process forecasts, signals, entries, settlements, fees, and cash releases in time order. Apply the fee schedule valid for the market and date, including rounding. Exclude or flag periods with unknown fees.

Maintain a ledger with model, city, station, market, source run, availability assumption, decision time, price, quantity, fees, result, and cash balance.

Reject future information, duplicate signals, incomplete target days, unresolved station mappings, stale quotes, and negative cash balances.

There must be no order-submission endpoint, deposit flow, wallet integration, or trading credential requirement.

**Acceptance:** An end-to-end replay produces a traceable ledger and reproduces its balances from recorded events.

## 9. Evaluate accuracy and strategy results

Create `src/weather_trades/report.py` and `reports/summary.md`.

Report all cities, including excluded rows and reasons. Show paired and unpaired results separately.

For forecast quality, report daily-high bias, mean absolute error, and correct outcome frequency against the contract's actual settlement value. Do not replace that value with a different station's observation.

For trading, report simulated net return, fees, win rate, drawdown, exposure, turnover, rejected entries, and capital utilization. Show results by city, station, model, month, and forecast lead.

Split each usable timeline chronologically into development and untouched evaluation periods. Publish exact boundaries before tuning. If data is too sparse, state that instead of reporting a strong conclusion.

Do not tune on the evaluation period or remove losing cities. Show sensitivity to forecast-release lag, trading delay, spreads, and fills. Account for shared weather systems when describing uncertainty; cities are not independent samples.

A more accurate temperature forecast does not automatically produce more profitable trades. Evaluate both questions separately.

## 10. Proposed repository layout and execution sequence

```text
config/
  market-classification.csv
  stations.csv
  strategy.json
src/weather_trades/
  cli.py
  markets.py
  stations.py
  forecasts.py
  history.py
  fees.py
  simulator.py
  report.py
docs/
  implementation-plan.md
  methodology.md
reports/
  coverage.csv
  source-availability.csv
  summary.md
```

These paths and commands are planned; they do not exist as functioning software yet.

1. Implement `python -m weather_trades.cli inventory` to enumerate all markets and cities.
2. Implement `python -m weather_trades.cli stations` to build verified coordinate mappings.
3. Implement `python -m weather_trades.cli probe` to establish bounded source access and costs.
4. Implement `python -m weather_trades.cli acquire` to populate the approved free-data manifest.
5. Implement `python -m weather_trades.cli backtest` to replay the frozen comparison.
6. Implement `python -m weather_trades.cli report` to produce city coverage and comparative results.
7. Implement `python -m weather_trades.cli verify` for the smallest meaningful end-to-end source and ledger checks.

Keep compact metadata, configuration, reports, and checksums in Git. Do not commit bulk weather files, databases, credentials, or raw media. Avoid new paid storage. If durable bulk storage is required, report the resource decision before acquiring it.

## 11. Completion criteria

- All discoverable weather-market cities are reconciled to the coverage ledger.
- Every included contract uses verified station coordinates and the correct settlement rules.
- Paired model samples match by station, contract, date, and decision time.
- Forecasts include documented availability times or explicitly labeled timing assumptions.
- Historical prices, fees, quantities, delays, and cash constraints are represented.
- Every simulated trade has a reproducible source trail.
- Missing coverage and uncertain fills remain visible in final results.
- No real orders, deposits, purchases, or new paid infrastructure occur.
- Code is exercised with real data before any implementation-complete claim.
- Repository changes are verified on live GitHub main before publication is called complete.

## 12. Primary references

- [Kalshi public market data](https://docs.kalshi.com/getting_started/quick_start_market_data)
- [Kalshi historical data routing](https://docs.kalshi.com/getting_started/historical_data)
- [Kalshi minute candles](https://docs.kalshi.com/api-reference/market/get-market-candlesticks)
- [Kalshi fees](https://kalshi.com/fee-schedule)
- [Open-Meteo individual runs](https://open-meteo.com/en/docs/single-runs-api)
- [Open-Meteo model updates](https://open-meteo.com/en/docs/model-updates)
- [NOAA HRRR schedule and domains](https://www.emc.ncep.noaa.gov/emc/pages/numerical_forecast_systems/hrrr.php)
- [NOAA station metadata](https://www.ncei.noaa.gov/access/homr/)

Recheck source access, applicable fees, and historical product coverage during implementation. Documentation availability does not prove complete historical data.
