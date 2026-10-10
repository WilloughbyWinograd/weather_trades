# GFS versus HRRR: corrected forecast timing

Study: 2026-08-28 through 2026-10-08. Each model starts with $100 shared across cities.
No real orders, purchases, deposits, or new paid infrastructure were used.

**Forecast source availability is verified before simulated entries. Trade fills remain assumptions.**
The program reads the original public run files directly. It uses the exact stored temperature values and each run's completion marker.
These are operational forecasts, not reanalysis or later runs. This source path avoids assumptions about historical forecast API updates.
Each model acts after its own publication: the next one-minute poll, one minute for processing, and the declared execution delay.
The shared-time scenario waits until both models' files are available. Timing rules were fixed before calculating corrected returns.
See [every run's publication evidence](forecast-timing.csv), [source records](archive-runs.json), and [native NOAA checks](noaa-source-checks.json).
The one missing GFS run remains excluded from both models. No release time or forecast is fabricated for it.

## Verified source timing

Publication lags below cover the 18:00 UTC runs used for new signals. Every previous run is also checked.

| Model | Complete current runs | Minimum lag (hours) | Median lag (hours) | Maximum lag (hours) |
| --- | ---: | ---: | ---: | ---: |
| GFS | 42 | 5.41 | 5.46 | 6.69 |
| HRRR | 42 | 1.84 | 1.90 | 2.92 |

The late September 22 GFS run becomes eligible after its September 23 00:41:11 UTC completion marker, never at the former 23:00 UTC decision.
Native NOAA checks passed for 12 fields and 288 station values. Maximum temperature difference: 0.023023 degree Celsius.
The correction preserves stored temperature precision and uses NOAA's precise HRRR grid origin. This also corrects Trenton's selected cell.

## Reserved evaluation: September 25–October 8

These dates were reserved in the original protocol. This is a corrected rerun of previously viewed dates, not a new untouched evaluation.
The trade rule, price limits, fees, and portfolio limits remain unchanged. The source precision and publication timing are corrected.

| Model | Ending balance | Net profit | Trades | Wins | Fees |
| --- | ---: | ---: | ---: | ---: | ---: |
| GFS | $83.87 | $-16.13 | 28 | 8 | $6.58 |
| HRRR | $82.46 | $-17.54 | 35 | 12 | $8.12 |

## Full study: quoted-price scenario

| Model | Ending balance | Net profit | Trades | Wins | Fees | Maximum drawdown at cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GFS | $89.47 | $-10.53 | 93 | 30 | $20.94 | $83.45 |
| HRRR | $0.04 | $-99.96 | 27 | 2 | $5.73 | $99.96 |

These are simulated quoted fills after fees. Historical executable quantities are unknown.
Open positions are valued at purchase cost for drawdown. This does not measure changes in their resale value.

## Coverage

The study includes 24 cities and 984 paired city-days.
The inventory classifies 424 weather series and records 96 named cities or resort locations.
It combines current and retired series with all retrieved location-variable products.
Every discovered location remains in [coverage.csv](coverage.csv), with its eligibility and coordinate status.
Cities with only other weather products have no daily-high return. Empty international series cannot support a return estimate.
This is the initial six-week comparison, not the complete historical archive.

## Forecast accuracy

| Model | Period | Mean absolute error (degrees Fahrenheit) | Bias (degrees Fahrenheit) | Correct outcome |
| --- | --- | ---: | ---: | ---: |
| GFS | all | 2.785 | -0.361 | 26.2% |
| GFS | evaluation | 2.660 | -0.963 | 29.8% |
| HRRR | all | 2.527 | -1.197 | 30.3% |
| HRRR | evaluation | 2.397 | -1.338 | 32.7% |

## Sensitivity and portfolio constraints

| Model | Scenario | Ending balance | Trades | Net profit |
| --- | --- | ---: | ---: | ---: |
| GFS | conservative | $71.75 | 45 | $-28.25 |
| GFS | volume_capped | $96.11 | 45 | $-3.89 |
| GFS | paired_ready | $89.47 | 93 | $-10.53 |
| GFS | delay_5m | $74.82 | 94 | $-25.18 |
| GFS | delay_15m | $54.84 | 95 | $-45.16 |
| GFS | cent_fees | $89.08 | 93 | $-10.92 |
| GFS | development | $105.60 | 65 | $5.60 |
| GFS | evaluation | $83.87 | 28 | $-16.13 |
| GFS | evaluation_paired_ready | $83.87 | 28 | $-16.13 |
| GFS | evaluation_conservative | $92.30 | 11 | $-7.70 |
| GFS | evaluation_volume_capped | $94.64 | 11 | $-5.36 |
| GFS | unconstrained | Not a $100 portfolio | 167 | $-105.06 |
| HRRR | conservative | $122.22 | 63 | $22.22 |
| HRRR | volume_capped | $71.02 | 59 | $-28.98 |
| HRRR | paired_ready | $20.50 | 102 | $-79.50 |
| HRRR | delay_5m | $0.03 | 72 | $-99.97 |
| HRRR | delay_15m | $19.82 | 103 | $-80.18 |
| HRRR | cent_fees | $0.00 | 26 | $-100.00 |
| HRRR | development | $0.04 | 27 | $-99.96 |
| HRRR | evaluation | $82.46 | 35 | $-17.54 |
| HRRR | evaluation_paired_ready | $50.48 | 35 | $-49.52 |
| HRRR | evaluation_conservative | $118.38 | 21 | $18.38 |
| HRRR | evaluation_volume_capped | $109.48 | 21 | $9.48 |
| HRRR | unconstrained | Not a $100 portfolio | 225 | $-313.74 |
| GFS | civil_day | $100.41 | 92 | $0.41 |
| HRRR | civil_day | $0.04 | 27 | $-99.96 |

The conservative scenario adds two cents, uses the highest ask, and requires positive interval volume. It still assumes a fill.
The volume-capped scenario also limits purchases to that minute's reported volume. This remains an assumed fill, not historical depth.
Zero fills leave either account at $100. Volume does not establish that our order could have filled.
Each independent phase starts at $100. The unconstrained diagnostic ignores cash and position limits; its aggregate profit requires more capital.
The baseline allows five open positions and spends at most $5 per trade, including fees.
Capital stays locked until recorded settlement. Simultaneous entries sort by city name, so allocation is unequal across cities.

## Every included city

| City | Station | Paired days | GFS error (degrees Fahrenheit) | HRRR error (degrees Fahrenheit) | GFS trades / profit | HRRR trades / profit |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Atlanta | KATL | 41 | 3.08 | 1.99 | 9 / $-24.71 | 1 / $-4.81 |
| Austin | KAUS | 41 | 1.77 | 3.76 | 5 / $-1.92 | 0 / $0.00 |
| Boston | KBOS | 41 | 2.53 | 2.25 | 5 / $-11.47 | 3 / $-0.51 |
| Chicago | KMDW | 41 | 1.99 | 2.76 | 10 / $33.08 | 3 / $-9.95 |
| Dallas | KDFW | 41 | 1.71 | 1.72 | 2 / $-9.54 | 3 / $-14.55 |
| Denver | KDEN | 41 | 2.04 | 2.00 | 7 / $10.10 | 3 / $-5.01 |
| Houston | KHOU | 41 | 2.25 | 2.07 | 7 / $22.10 | 2 / $-9.62 |
| Las Vegas | KLAS | 41 | 3.28 | 1.19 | 0 / $0.00 | 0 / $0.00 |
| Los Angeles | KLAX | 41 | 2.37 | 2.33 | 5 / $8.69 | 1 / $-4.97 |
| Louisville | KSDF | 41 | 2.19 | 1.71 | 2 / $-0.92 | 0 / $0.00 |
| Miami | KMIA | 41 | 2.22 | 3.27 | 8 / $4.28 | 1 / $-5.00 |
| Minneapolis | KMSP | 41 | 3.07 | 2.31 | 3 / $-14.27 | 3 / $-11.60 |
| New Orleans | KMSY | 41 | 3.79 | 2.34 | 2 / $-9.80 | 1 / $-5.00 |
| New York City | KNYC | 41 | 3.95 | 2.08 | 3 / $-14.65 | 1 / $-4.98 |
| Newark | KEWR | 41 | 1.77 | 2.31 | 3 / $7.69 | 0 / $0.00 |
| Oklahoma City | KOKC | 41 | 2.67 | 2.41 | 5 / $-9.35 | 1 / $-4.58 |
| Philadelphia | KPHL | 41 | 1.85 | 3.30 | 4 / $41.71 | 1 / $-5.00 |
| Phoenix | KPHX | 41 | 3.16 | 2.08 | 2 / $-9.33 | 0 / $0.00 |
| San Antonio | KSAT | 41 | 2.24 | 1.75 | 3 / $-14.71 | 0 / $0.00 |
| San Diego | KSAN | 41 | 3.23 | 2.37 | 1 / $-4.97 | 0 / $0.00 |
| San Francisco | KSFO | 41 | 7.69 | 7.30 | 0 / $0.00 | 0 / $0.00 |
| Seattle | KSEA | 41 | 3.53 | 2.58 | 3 / $-14.20 | 2 / $-9.52 |
| Trenton | KTTN | 41 | 2.31 | 2.22 | 0 / $0.00 | 0 / $0.00 |
| Washington, DC | KDCA | 41 | 2.15 | 2.55 | 4 / $1.66 | 1 / $-4.86 |

City profits are contributions to the shared portfolio. They are not independent $100 city portfolios.

## Interpretation and remaining work

This experiment compares a fixed forecast-revision rule against archived forecasts, later quotes, and settled outcomes.
Forecast accuracy and trading profit are separate results. A model can improve one without improving the other.
The short period and correlated weather across cities prevent a reliable long-term profitability conclusion.
Every consumed run file and completion marker predates its simulated decision. The saved binary ranges reproduce the extracted values exactly.
Publication evidence applies to direct public archive access. Historical API routing and client download logs are not required by this source path.
Polling, processing, and order latency remain simulated. This study does not establish an advantage that lasts only seconds.
Forecasts use hourly maxima at the settlement station coordinates. Hourly values can miss brief temperature extremes.
Station coordinates use current metadata. Historical relocations and source-day definitions require further auditing.
The study compares the previous day's 12 and 18 UTC runs. HRRR's intervening short runs cannot cover the complete target day.
Earlier history, other daily update pairs, and live executable depth remain separate extensions.

## Reproduce and inspect

Run `python -m weather_trades.cli replay` after installation for an offline replay of the compact saved inputs.
See [methodology](../docs/methodology.md), [exact results](results.json), [city results](by-city.csv), and [source requests](source-manifest.csv).
The ledger files contain every accepted and rejected signal. Forecast and source-availability files retain timing and station information.
Source attribution: Open-Meteo, NOAA GFS, NOAA HRRR, Kalshi, and The Weather Company.
