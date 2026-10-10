# Selling-rule comparison

Holding to settlement had the highest average result for both models. Every tested selling rule lost money after fees on both the matched sample and each rule's available sample. Among timed sales, six hours was least negative for GFS and three hours was least negative for HRRR.

Average net dollars per paper entry, including purchase and sale fees. Each entry has a maximum budget of $5; whole-contract sizing can leave part of that budget unused. The same tweet-method entries and forecast-publication evidence are retained.

| Exit rule | GFS | HRRR |
| --- | ---: | ---: |
| 15 minutes | -0.83 | -0.85 |
| 60 minutes | -0.87 | -0.80 |
| 3 hours | -0.73 | -0.66 |
| 6 hours | -0.64 | -0.73 |
| Gain 5 cents / lose 5 cents | -0.78 | -0.80 |
| Gain 10 cents / lose 5 cents | -0.72 | -0.80 |
| Settlement | +0.41 | -0.05 |

The table compares only entries with an observed exit under every rule: GFS 219 of 266 eligible entries; HRRR 278 of 318 eligible entries. This matches entries across exit rules but can favor markets with more complete quote records.

Across every eligible entry, settlement averaged GFS +0.03 dollars (266 entries); HRRR -0.36 dollars (318 entries). The stronger matched-sample GFS result therefore depends on excluding entries with missing selling quotes. This test does not establish a reliable profitable exit.

## Earlier selection and later results

Rules were selected using August 28–September 24 and then assessed on September 25–October 8. These dates had already been studied, so the later comparison is a stability check, not a new untouched evaluation.

| Model | Selected on earlier dates | Earlier average | Later average | Later entries | Later 95 percent interval |
| --- | --- | ---: | ---: | ---: | --- |
| GFS | Settlement | +0.15 | +1.14 | 58 | -1.10 to +3.28 |
| HRRR | Settlement | -0.23 | +0.24 | 108 | -1.45 to +1.93 |

Intervals resample target dates together to preserve dependence between cities on the same day. They are exploratory and do not adjust for choosing the best of seven rules.

## Exit definitions

- Timed exits use the first valid positive bid at or after the specified time, allowing up to 15 additional minutes. No earlier quote is carried forward.
- Profit targets and stops compare the observed minute-close bid with the initial ask. Their thresholds are gross price changes, before fees. A trigger schedules a sale at the first valid quote at least one minute later, within the same 15-minute wait. Prices can move beyond the threshold before that quote.
- Both target-and-stop rules have a six-hour time limit. Missing minute records can conceal threshold crossings; no unobserved intraminute trigger is assumed.
- Settlement uses the verified $1 or $0 contract payout and has no sale or settlement fee.

The [July 7, 2026 fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf) and the [recorded override audit](../fee-evidence.json) determine fees. A purchase and a sale both incur the standard taker fee. This comparison assumes quoted fills because historical order-book quantities are unavailable; it is not a cash-constrained portfolio or a live trading result.

## Quote coverage and sensitivity

The table below uses all observed exits for each rule. These samples differ, so compare them with the matched table above rather than ranking them alone.

| Model | Exit rule | Observed / eligible | Unresolved | Average net dollars | Average holding minutes |
| --- | --- | ---: | ---: | ---: | ---: |
| GFS | 15 minutes | 255/266 | 11 | -0.92 | 17.0 |
| GFS | 60 minutes | 246/266 | 20 | -0.92 | 62.2 |
| GFS | 3 hours | 250/266 | 16 | -0.82 | 181.5 |
| GFS | 6 hours | 250/266 | 16 | -0.76 | 361.5 |
| GFS | Gain 5 cents / lose 5 cents | 258/266 | 8 | -0.87 | 173.3 |
| GFS | Gain 10 cents / lose 5 cents | 258/266 | 8 | -0.85 | 206.5 |
| GFS | Settlement | 266/266 | 0 | +0.03 | 2169.0 |
| HRRR | 15 minutes | 308/318 | 10 | -0.88 | 17.7 |
| HRRR | 60 minutes | 303/318 | 15 | -0.84 | 61.8 |
| HRRR | 3 hours | 306/318 | 12 | -0.74 | 181.9 |
| HRRR | 6 hours | 307/318 | 11 | -0.81 | 361.7 |
| HRRR | Gain 5 cents / lose 5 cents | 308/318 | 10 | -0.88 | 191.3 |
| HRRR | Gain 10 cents / lose 5 cents | 309/318 | 9 | -0.87 | 220.5 |
| HRRR | Settlement | 318/318 | 0 | -0.36 | 2402.9 |

## Reproduction and evidence

[Frozen rules](../../config/exit-comparison.json), [every policy outcome](ledger.csv), [all comparison groups](comparison.csv), [complete summary](summary.json), [source quotes and receipts](inputs.json), and [verification](verification.json). The [entry study](../tweet-price-response/summary.md) documents the Celsius-to-Fahrenheit adaptation, hourly polling, original run files, and one forecast comparison per day.

Run `python -m weather_trades.cli replay-exits` to reproduce the calculation without network access. `compare-exits` reacquires public quote windows. `verify-exits` checks preserved responses, entry identity, chronology, independent fee arithmetic, and an identical replay with network connections disabled; it requires the local raw response cache.
