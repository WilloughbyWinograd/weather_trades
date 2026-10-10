# Frozen research protocol

This is personal, hypothetical research. No trading interface or credentials are implemented. Each model starts with $100 shared across all cities. The committed strategy configuration records the protocol freeze, before any profitability calculation.

## Initial study window

Evaluate August 28 through October 8, 2026, inclusive. Development dates end September 24; the original reserved evaluation starts September 25. The corrected calculation reuses previously viewed dates. It is not a new untouched evaluation. These contiguous dates are chosen for recent settled markets, the published July fee schedule, and the free forecast request budget. No parameter tuning is permitted after viewing results. The fixed window is retained when a source run is missing; dates are not replaced. This initial window is not the full available historical archive.

The comparison uses 12 and 18 UTC runs initialized on the day before the target date. Each model acts after its own 18 UTC distribution is complete. Both required runs must have publication evidence. The shared-time sensitivity waits for both models. Stations, target dates, signals, fees, and portfolio rules are identical.

The decision follows the first whole-minute poll at or after the completion marker, plus one minute for processing. Entry then follows the declared delay and a later completed price interval. No assumed five-, six-, or seven-hour forecast release delay remains in the corrected calculation. The 18 UTC run is the latest eligible complete-day run at these decisions. Intervening HRRR runs extend only 18 hours and cannot cover the entire target day.

## Forecast and station evidence

Read `temperature_2m.om` and `meta.json` from Open-Meteo's public `data_run/<model>/<YYYY/MM/DD/HHmmZ>/` distribution. The model identifiers are `ncep_gfs013` and `ncep_hrrr_conus`. These files preserve specific operational runs. Do not use reanalysis, best-match, seamless forecasts, observations, or later runs as substitutes.

Open-Meteo documents that it writes the run metadata after completing the run-file distribution. The program requires this completion marker and its original reference time, valid times, and temperature-variable entry. The marker's object timestamp must follow the temperature object's timestamp. The marker must be a single-part object with a matching content checksum. Amazon S3 provides strong read-after-write consistency. Together, these records establish that the exact source distribution existed by the marker time. This is a conservative available-by time, not a claim about the earliest native NOAA release.

Conditional byte-range requests pin each temperature file to its entity tag. The program checks the returned byte range, timestamp, and identity. It checks both object identities again after extraction. Every retained byte range has a checksum. The full source audit re-decodes those bytes without network access. Missing markers, mismatched identities, later rewrites, and incomplete fields cannot inherit an assumed release time.

The evidence concerns direct access to these public files. It does not claim historical forecast API routing, an actual client download, or measured processing latency. The declared polling and processing times remain simulated.

All 168 requested model runs have source records: 83 GFS runs and 84 HRRR runs are complete. The GFS run initialized September 14 at 12 UTC is absent. The 24 affected September 15 city-days remain excluded from both models. No replacement date or run is selected.

Extract the nearest model grid cell to each settlement station. Preserve stored 32-bit Celsius values, with no API rounding or elevation adjustment. Open-Meteo's pinned grid definition identifies dimensions and orientation. Native NOAA HRRR headers supply the precise grid origin and spacing. Rounded bounds selected an adjacent Trenton cell; the corrected extraction uses the native coordinates.

The source check compares both models and cycles on the first, middle, and final source dates. Twelve native NOAA fields provide 288 station comparisons at forecast lead 24 hours. It independently decodes initialization, valid time, level, units, and grid coordinates. The 0.051-degree Celsius tolerance accommodates the archive's temperature quantization. This is a bounded independent check; every consumed hour is also checked against the exact stored archive bytes.

The maximum of hourly samples can miss a between-hour temperature maximum. Native NOAA values and the archive's compressed values can differ slightly. The former forecast API rounded values to 0.1 degree Celsius. Corrected signals therefore can change from both source precision and publication timing. No trading threshold or portfolio limit was adjusted in response to returns.

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
- [Open-Meteo run-file publication sequence and retention](https://github.com/open-meteo/open-data#updates-to-real-time-weather-forecasts)
- [Pinned Open-Meteo grid implementation](https://github.com/open-meteo/open-meteo/blob/f625df2c2b2d29d7837b1c71660fb226b1864f9b/Sources/App/Gfs/GfsDomain.swift)
- [Amazon S3 consistency](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html#ConsistencyModel)
- [NOAA HRRR products and schedule](https://www.emc.ncep.noaa.gov/emc/pages/numerical_forecast_systems/hrrr.php)
- [Open-Meteo noncommercial limits and terms](https://open-meteo.com/en/terms)

Forecast data attribution: Open-Meteo, NOAA GFS and NOAA HRRR, under Open-Meteo's CC BY 4.0 data license. Public file access is used only for this personal hypothetical study.

## Source failures and reproducibility

An absent archived run remains a source gap. Invalid source identities or chronology stop acquisition. Every requested station, day, model, run, and day definition receives a row. Incomplete acquisition stops the replay. Missing runs exclude affected city-days from both sides of the paired comparison.

The compact replay snapshot preserves contract metadata and the exact quote windows used by every scenario. It binds the strategy, station table, forecast reductions, settlement validation, and fee audit by checksum. The offline replay does not contact a data provider. Raw response files remain outside Git. Public request checksums, exact run-file identities, and binary-range checksums are recorded in the committed manifests. Native NOAA check receipts record the exact field range and checksum. The public archive has limited retention, so full reacquisition is time-limited. Compact offline replay does not depend on that retention.

Each scenario reports maximum committed principal and average committed principal from first entry through final settlement. The latter excludes time before the first entry.
