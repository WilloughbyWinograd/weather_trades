# HRRR updated-forecast range

Buying the updated forecast range reduced total net profit by $71.63 in this historical sample. The tables also compare the same city-days to account for the changed set of eligible trades.

One change: buy the contract containing HRRR's updated maximum temperature instead of moving one whole Celsius degree from its previous forecast. All other entry and settlement rules are retained.

August 28–October 8, 2026. Each paper entry has a maximum budget of 5 dollars including purchase fees. Before-fee profit uses the same contract quantities as the after-fee calculation.

| Entry rule | Entries | Wins | Before fees | Purchase fees | After fees | Average after fees |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original one-degree step | 318 | 93 | $-41.65 | $72.59 | $-114.24 | $-0.36 |
| Updated forecast range | 303 | 84 | $-116.81 | $69.06 | $-185.87 | $-0.61 |

## Same city-days

Both rules could trade on 288 city-days. Contract choice can change quote availability, the entry price, the exact first quoted minute, and eligibility under the unchanged 5–60 cent price band.

| Entry rule | Before fees | After fees | Average after fees |
| --- | ---: | ---: | ---: |
| Original one-degree step | $-12.84 | $-78.78 | $-0.27 |
| Updated forecast range | $-135.24 | $-200.41 | $-0.70 |

The updated rule changes average net profit by $-0.42 per matched entry. Its descriptive 95 percent date-cluster bootstrap interval is $-1.31 to $+0.38 (2,000 resamples; fixed seed).

## Coverage

| Entry rule | Revision signals | Eligible | No initial quote | Initial ask outside band |
| --- | ---: | ---: | ---: | ---: |
| Original one-degree step | 454 | 318 | 94 | 42 |
| Updated forecast range | 454 | 303 | 102 | 49 |

## Earlier and later dates

| Period | Entry rule | Entries | Before fees | After fees |
| --- | --- | ---: | ---: | ---: |
| August 28–September 24 | Original one-degree step | 198 | $-64.13 | $-109.30 |
| August 28–September 24 | Updated forecast range | 188 | $-54.68 | $-97.32 |
| September 25–October 8 | Original one-degree step | 120 | $+22.48 | $-4.94 |
| September 25–October 8 | Updated forecast range | 115 | $-62.13 | $-88.55 |

## Method and evidence

The revision threshold remains 0.5 degrees Celsius. Updated temperatures convert directly to Fahrenheit and round to the nearest integer, with half away from zero, before selecting the contract range. No whole-Celsius rounding or requirement for a changed range is added. Both rules consume the same original HRRR forecast files and publication markers. Hourly polling, one-minute processing, delayed quote selection, five-minute quote wait, and holding to settlement remain unchanged.

Decision inputs exclude settlement outcomes. Each rule uses the first valid ask in its entry window and rejects that quote if it is outside the unchanged price band. Missing quotes remain exclusions. There is no selection using the later settlement result. Purchase fees use the existing dated schedule and verified overrides; settlement has no sale fee.

These dates and some individual outcomes were already examined before proposing this rule. The change was frozen before retrieving its quotes or calculating its aggregate results, but this remains an exploratory comparison on previously studied data. Quoted fills and sufficient capital for every entry are assumed. This is not a cash-constrained portfolio or a live trading result.

[Frozen change](../../config/hrrr-updated-range.json), [signals and exclusions](signals.csv), [settlement ledger](ledger.csv), [comparison groups](comparison.csv), [complete summary](summary.json), [quote inputs and receipts](inputs.json), and [verification](verification.json). Original [entry rules](../tweet-price-response/summary.md) and [settlement comparison](../exit-comparison/summary.md) remain unchanged.

Run `python -m weather_trades.cli replay-hrrr-range` for offline reproduction. `compare-hrrr-range` acquires public quotes. `verify-hrrr-range` verifies preserved raw responses, unchanged signal clocks and baseline trades, independent money arithmetic, and an identical replay with network access disabled.
