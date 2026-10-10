# GFS versus HRRR: initial six-week backtest

Study: 2026-08-28 through 2026-10-08. Each model starts with $100 shared across cities.
No real orders, purchases, deposits, or new paid infrastructure were used.

**Status: exploratory simulation with assumed forecast availability and assumed fills.**
The inputs are specific archived GFS and HRRR runs, using Open-Meteo's processed hourly values.
They are not reanalysis or a later run. Historical accessibility at each entry is unverified.
The baseline assumes availability five hours after initialization; six- and seven-hour scenarios test that assumption.
The results do not establish what a script could have received and traded at those exact times.
A subsequent [archive-object audit](publication-probes.json) found that every studied 18 UTC GFS temperature object was modified after the baseline's first entry time.
Those timestamps do not establish first API availability, but the five-hour baseline does not meet the required historical-access verification.

## Independent evaluation: September 25–October 8

These dates were reserved before calculating performance. Strategy parameters were not tuned after viewing results.

| Model | Ending balance | Net profit | Trades | Wins | Fees |
| --- | ---: | ---: | ---: | ---: | ---: |
| GFS | $51.31 | $-48.69 | 29 | 7 | $6.61 |
| HRRR | $47.58 | $-52.42 | 35 | 8 | $7.87 |

## Full study: quoted-price scenario

| Model | Ending balance | Net profit | Trades | Wins | Fees | Maximum drawdown at cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GFS | $105.26 | $5.26 | 93 | 32 | $20.79 | $71.85 |
| HRRR | $0.02 | $-99.98 | 67 | 15 | $14.60 | $99.98 |

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
| GFS | all | 2.782 | -0.271 | 26.6% |
| GFS | evaluation | 2.643 | -0.873 | 30.1% |
| HRRR | all | 2.509 | -1.144 | 30.5% |
| HRRR | evaluation | 2.381 | -1.287 | 33.3% |

## Sensitivity and portfolio constraints

| Model | Scenario | Ending balance | Trades | Net profit |
| --- | --- | ---: | ---: | ---: |
| GFS | conservative | $77.74 | 38 | $-22.26 |
| GFS | volume_capped | $106.77 | 38 | $6.77 |
| GFS | release_6h | $100.88 | 94 | $0.88 |
| GFS | release_7h | $126.94 | 92 | $26.94 |
| GFS | delay_5m | $101.43 | 94 | $1.43 |
| GFS | delay_15m | $72.06 | 95 | $-27.94 |
| GFS | cent_fees | $104.92 | 93 | $4.92 |
| GFS | development | $153.95 | 64 | $53.95 |
| GFS | evaluation | $51.31 | 29 | $-48.69 |
| GFS | evaluation_conservative | $130.02 | 8 | $30.02 |
| GFS | evaluation_volume_capped | $124.26 | 8 | $24.26 |
| GFS | unconstrained | Not a $100 portfolio | 152 | $-76.87 |
| HRRR | conservative | $0.00 | 49 | $-100.00 |
| HRRR | volume_capped | $70.05 | 54 | $-29.95 |
| HRRR | release_6h | $0.02 | 30 | $-99.98 |
| HRRR | release_7h | $0.00 | 25 | $-100.00 |
| HRRR | delay_5m | $0.05 | 79 | $-99.95 |
| HRRR | delay_15m | $51.43 | 100 | $-48.57 |
| HRRR | cent_fees | $0.02 | 62 | $-99.98 |
| HRRR | development | $2.06 | 64 | $-97.94 |
| HRRR | evaluation | $47.58 | 35 | $-52.42 |
| HRRR | evaluation_conservative | $73.97 | 19 | $-26.03 |
| HRRR | evaluation_volume_capped | $94.74 | 19 | $-5.26 |
| HRRR | unconstrained | Not a $100 portfolio | 219 | $-378.37 |
| GFS | civil_day | $94.69 | 93 | $-5.31 |
| HRRR | civil_day | $0.01 | 64 | $-99.99 |

The conservative scenario adds two cents, uses the highest ask, and requires positive interval volume. It still assumes a fill.
The volume-capped scenario also limits purchases to that minute's reported volume. This remains an assumed fill, not historical depth.
Zero fills leave either account at $100. Volume does not establish that our order could have filled.
Each independent phase starts at $100. The unconstrained diagnostic ignores cash and position limits; its aggregate profit requires more capital.
The baseline allows five open positions and spends at most $5 per trade, including fees.
Capital stays locked until recorded settlement. Simultaneous entries sort by city name, so allocation is unequal across cities.

## Every included city

| City | Station | Paired days | GFS error (degrees Fahrenheit) | HRRR error (degrees Fahrenheit) | GFS trades / profit | HRRR trades / profit |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Atlanta | KATL | 41 | 3.16 | 2.02 | 6 / $-8.92 | 4 / $1.70 |
| Austin | KAUS | 41 | 1.75 | 3.73 | 7 / $1.94 | 3 / $1.26 |
| Boston | KBOS | 41 | 2.48 | 2.24 | 5 / $3.30 | 3 / $-14.57 |
| Chicago | KMDW | 41 | 2.01 | 2.75 | 13 / $19.23 | 8 / $-26.69 |
| Dallas | KDFW | 41 | 1.73 | 1.69 | 2 / $23.13 | 5 / $-24.44 |
| Denver | KDEN | 41 | 2.01 | 1.99 | 4 / $23.00 | 4 / $10.71 |
| Houston | KHOU | 41 | 2.23 | 2.07 | 5 / $-10.42 | 3 / $-14.82 |
| Las Vegas | KLAS | 41 | 3.20 | 1.19 | 1 / $-4.86 | 1 / $3.38 |
| Los Angeles | KLAX | 41 | 2.36 | 2.31 | 4 / $-2.77 | 3 / $-0.94 |
| Louisville | KSDF | 41 | 2.23 | 1.72 | 0 / $0.00 | 1 / $7.12 |
| Miami | KMIA | 41 | 2.27 | 3.22 | 7 / $8.19 | 8 / $-7.67 |
| Minneapolis | KMSP | 41 | 3.10 | 2.29 | 3 / $24.33 | 3 / $-0.43 |
| New Orleans | KMSY | 41 | 3.70 | 2.32 | 2 / $3.37 | 4 / $-19.27 |
| New York City | KNYC | 41 | 4.02 | 2.09 | 5 / $-24.51 | 4 / $-7.78 |
| Newark | KEWR | 41 | 1.79 | 2.29 | 3 / $-2.31 | 3 / $-10.20 |
| Oklahoma City | KOKC | 41 | 2.70 | 2.37 | 4 / $-19.57 | 2 / $-6.80 |
| Philadelphia | KPHL | 41 | 1.82 | 3.26 | 6 / $-0.85 | 1 / $26.07 |
| Phoenix | KPHX | 41 | 3.10 | 2.05 | 2 / $-0.68 | 0 / $0.00 |
| San Antonio | KSAT | 41 | 2.21 | 1.74 | 4 / $-19.62 | 1 / $7.36 |
| San Diego | KSAN | 41 | 3.18 | 2.35 | 1 / $-4.87 | 1 / $-4.57 |
| San Francisco | KSFO | 41 | 7.60 | 7.25 | 0 / $0.00 | 0 / $0.00 |
| Seattle | KSEA | 41 | 3.59 | 2.58 | 2 / $-9.79 | 4 / $-14.76 |
| Trenton | KTTN | 41 | 2.35 | 2.12 | 1 / $-4.75 | 0 / $0.00 |
| Washington, DC | KDCA | 41 | 2.17 | 2.55 | 6 / $12.70 | 1 / $-4.67 |

City profits are contributions to the shared portfolio. They are not independent $100 city portfolios.

## Interpretation and remaining work

This experiment compares a fixed forecast-revision rule against archived forecasts, later quotes, and settled outcomes.
Forecast accuracy and trading profit are separate results. A model can improve one without improving the other.
The short period and correlated weather across cities prevent a reliable long-term profitability conclusion.
Historical forecast publication times are assumed. This study does not test an advantage that lasts only seconds.
Forecasts use hourly maxima at the settlement station coordinates. Hourly values can miss brief temperature extremes.
Station coordinates use current metadata. Historical relocations and source-day definitions require further auditing.
The common evening schedule, earlier archive, native update schedules, and live executable depth remain separate extensions.

## Reproduce and inspect

Run `python -m weather_trades.cli replay` after installation for an offline replay of the compact saved inputs.
See [methodology](../docs/methodology.md), [exact results](results.json), [city results](by-city.csv), and [source requests](source-manifest.csv).
The ledger files contain every accepted and rejected signal. Forecast and source-availability files retain timing and station information.
Source attribution: Open-Meteo, NOAA GFS, NOAA HRRR, Kalshi, and The Weather Company.
