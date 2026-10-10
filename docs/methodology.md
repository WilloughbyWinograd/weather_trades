# Frozen research protocol

This is personal, hypothetical research. No trading interface or credentials are implemented. Each model starts with $100 shared across all cities. The committed strategy configuration records the protocol freeze, before any profitability calculation.

## Initial study window

Evaluate August 28 through October 8, 2026, inclusive. Development dates end September 24; untouched evaluation starts September 25. These contiguous dates are chosen for recent settled markets, the published July fee schedule, and the free forecast request budget. No parameter tuning is permitted after viewing results. The fixed window is retained when a source run is missing; dates are not replaced. This initial window is not the full available historical archive.

The first comparison uses 12 and 18 UTC individual runs initialized on the day before the target date. Decisions occur at 23 UTC, assuming five hours for release of the 18 UTC run. Both models use identical runs, station locations, target dates and decision times. This common evening schedule is a restricted baseline, not a replay of every native update. Release timestamps are assumed, not historically observed. Sensitivities use six and seven hours and longer quote delays. The evaluation period also receives the same conservative fill scenario.

## Forecast and station evidence

Use Open-Meteo's explicitly selected `gfs_global` and `gfs_hrrr` single-run products. Never use best-match, seamless, reanalysis, or a current forecast in place of an archived run. Requests disable elevation adjustment and select the nearest grid cell. Retain returned grid coordinates, source request and checksum. Values are provider-processed hourly forecasts, not raw NOAA GRIB. The maximum of hourly samples can miss a between-hour maximum.

The single-run documentation supports run identity, not proof of historical accessibility. Open-Meteo's metadata documentation exposes the latest run's availability and recommends ten additional minutes for server propagation. It does not supply the missing per-run historical evidence for this study. Retrieval timestamps in the manifest record this research session, not past publication. Therefore the results must remain an exploratory simulation with assumed availability. A verified replay requires historical access evidence for every consumed run and field, along with a reproducible processing path. A later object modification timestamp alone cannot establish first availability or prove that an earlier copy did not exist.

After the initial calculation, all 168 study-run temperature objects were checked through the provider's public archive. Eighty-three of 84 GFS objects and all 84 HRRR objects were present. GFS object modification times followed initialization by 5.36–5.66 hours; HRRR by 1.84–2.77 hours. All 42 current-cycle GFS objects were modified after the first assumed baseline entry. The absent GFS object matches the missing run already excluded. This evidence leaves the five-hour baseline unsuitable for an exact-access claim. The predeclared six- and seven-hour sensitivities remain assumed-access simulations. No strategy parameters were changed in response to profitability.

A contract's own CLI identifier is joined to The Weather Company's dated station metadata. NOAA station metadata supplies coordinates. Current coordinate metadata is not an independently audited historical relocation record. Provider station labels can differ from older National Weather Service market definitions; earlier rules must not be silently inherited.

Domestic daily climate reports use midnight-to-midnight local standard time. Forecast extraction uses the timezone's January standard offset, and requires all 24 hourly samples in the target period. A local civil-day sensitivity tests daylight-saving ambiguity in the provider's day definition. Publication and source revisions are not assumed to have occurred at initialization.

## Signal and execution assumptions

A forecast revision of at least 0.5 degrees Celsius must change the predicted integer-Fahrenheit outcome. Forecasts are rounded to the nearest integer Fahrenheit, with half values away from zero, as an explicit strategy assumption for integer domestic reports. This is not a replacement for the contract's full-precision settlement rule. Buy the immediately adjacent outcome toward the revised forecast. Skip ambiguous, overlapping, unsupported or incomplete outcome sets.

Require a YES ask of 5–60 cents. At the first completed minute after the decision and one-minute delay, use the ask close. Search no more than five additional minutes; never backfill an earlier quote or choose the lowest price. A conservative scenario adds two cents, requires positive traded volume in the interval, and uses the interval's highest ask. A volume-capped sensitivity also limits whole-contract purchases to the reported interval volume. It is repeated on the evaluation period. None of these scenarios proves a fill: minute candles do not provide historical executable depth. A zero-fill scenario retains $100.

Each entry spends at most $5 including fees, using whole contracts. At most five positions may be open. One position is allowed per canonical city and target date. Same-time ties sort by canonical city and market identifier, never outcome or profitability. Hold positions until the recorded settlement timestamp; principal remains locked. All rejected signals remain in the ledger.

The July 7, 2026 fee PDF specifies `0.07 × quantity × price × (1-price)` and rounds total order cost to a centicent. Its example table displays cent-rounded fees. The rounding documentation distinguishes direct-member and non-direct-member precision. Use the formula's centicent precision as baseline and whole-cent rounding as a sensitivity. Require the retrieved series multiplier to equal one. Query all historical series fee changes and exhaust the event fee-change history. Stop if an override affects a studied series or event. The retrieved histories contain no such overrides. There is no settlement fee.

## Evaluation

Report paired forecast errors against the contract expiration value, per-city results, total fees, wins and losses, completed trades, drawdown measured with open positions at cost, capital-blocked signals, and unconstrained per-signal returns. Open-position-at-cost drawdown is not a mark-to-market risk estimate. Development and evaluation portfolios are also replayed independently from $100.

Reproduce ledger cash from chronological entry and settlement events. Reject incomplete days, future-entry quotes, nonfinite values, unmapped stations, unknown settlements, duplicate signals, and negative cash. Every result must trace to real cached requests. Every discovered weather series remains in the coverage files, even if it has no settled market or no supported daily-high product.

## Sources

- [Kalshi contract terms](https://assets.kalshi.com/contract_terms/GLOBALTEMPERATURE.pdf)
- [Kalshi fee schedule, effective July 7, 2026](https://kalshi.com/docs/kalshi-fee-schedule.pdf)
- [Kalshi fee rounding](https://docs.kalshi.com/getting_started/fee_rounding)
- [Kalshi historical series fee changes](https://docs.kalshi.com/api-reference/exchange/get-series-fee-changes)
- [Kalshi event fee changes](https://docs.kalshi.com/api-reference/events/get-event-fee-changes)
- [The Weather Company settlement source](https://weather.com/kalshi)
- [NOAA weather station API](https://www.weather.gov/documentation/services-web-api)
- [National Weather Service climate observation day](https://www.weather.gov/lot/weather_observations_faq)
- [Open-Meteo single-run archive](https://open-meteo.com/en/docs/single-runs-api)
- [Open-Meteo availability semantics](https://open-meteo.com/en/docs/model-updates)
- [Open-Meteo noncommercial limits and terms](https://open-meteo.com/en/terms)

Forecast data attribution: Open-Meteo, NOAA GFS and NOAA HRRR, under Open-Meteo's CC BY 4.0 data license. The free API is used only for this personal hypothetical study.

## Source failures and reproducibility

An explicit archived-run error remains a source gap, even when the server returns HTTP status 200. Every requested station, day, model, run, and day definition receives a row. Incomplete acquisition stops the replay. Missing runs exclude affected city-days from both sides of the paired comparison.

The compact replay snapshot preserves contract metadata and the exact quote windows used by every scenario. It binds the strategy, station table, forecast reductions, settlement validation, and fee audit by checksum. The offline replay does not contact a data provider. Raw response files remain outside Git; their public requests and checksums are recorded in the source manifest.

Each scenario reports maximum committed principal and average committed principal from first entry through final settlement. The latter excludes time before the first entry.
