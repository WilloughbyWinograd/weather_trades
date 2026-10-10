# Tweet-method price response

August 28–October 8, 2026; 24 cities and 984 paired city-days. Values below are average quoted ask-price changes, in cents per contract.

| Model | After 15 minutes | Observations | After 60 minutes | Observations |
| --- | ---: | ---: | ---: | ---: |
| GFS | -0.04 | 109 | -0.22 | 116 |
| HRRR | +0.37 | 117 | +0.52 | 156 |

Exact-minute quotes are absent for many signals. Those missing observations are excluded from the averages, so these results describe only the observed subset.

## Entry rule

The [original tweet](https://x.com/xmayeth/status/2108586474715185534) describes buying after tomorrow's maximum temperature changes by at least 0.5 degrees Celsius. It selects the outcome one degree toward the new forecast and restricts the initial price to 5–60 cents. It supplies no exit rule.

This Kalshi adaptation rounds the previous forecast to a whole Celsius degree, moves one Celsius degree in the revision direction, converts that target to Fahrenheit, and selects the bracket containing its rounded integer. Both roundings use half away from zero. This reproduces the tweet's 16.8-to-15.8 degree example by selecting 16 degrees Celsius. It does not require a change of Fahrenheit bracket.

The existing 12:00-to-18:00 Coordinated Universal Time run pair is retained for each model, using the original archived forecast files. This is one update comparison per target day, not every model cycle or the tweet's complete Polymarket deployment. The existing validated city universe and local standard-day definitions are retained. The missing Global Forecast System run excludes September 15 for both models. These dates were analyzed before this retest; this is not a new untouched evaluation.

## Timing and measurements

Each model checks at the next whole hour after both consumed run files have completion markers, allows one minute for processing, then one minute before the first complete quote candle. The first valid quote is used within a five-minute wait; it is rejected if its ask is outside the price band. Forecasts must be ready before the target day and the selected contract must already be open.

Later quotes are sampled exactly 15 and 60 minutes after the initial quote. There is no forward filling or selection by later price. Every eligible signal is retained, without cash or position limits. Prices are equally weighted across signals. No sale, portfolio return, fees, or executable quantity is assumed.

| Model | Minutes | Observed / eligible | Median ask change | Later bid minus initial ask | Initial candles with zero volume |
| --- | ---: | ---: | ---: | ---: | ---: |
| GFS | 15 | 109/266 | +0.00 | -2.26 | 88 |
| GFS | 60 | 116/266 | +0.00 | -1.94 | 97 |
| HRRR | 15 | 117/318 | +0.00 | -1.84 | 102 |
| HRRR | 60 | 156/318 | +0.00 | -1.83 | 134 |

The bid-minus-ask column shows the average price gap after crossing the quoted spread. It is not realized profit. Zero-volume candles can contain quoted prices but do not demonstrate a trade or available size. Neither price movement nor this comparison establishes that the forecast caused the movement.

## Evidence and reproduction

[Frozen rules](../../config/tweet-price-response.json), [all signals and exclusions](signals.csv), [individual measurements](samples.csv), [paired-date exclusions](exclusions.csv), [complete summary](summary.json), [compact inputs and source receipts](inputs.json), and [verification](verification.json). Forecast identity and publication evidence remain in the [run manifest](../archive-runs.json) and [forecast table](../forecast-samples.csv).

Run `python -m weather_trades.cli replay-tweet-prices` to reproduce the report from committed inputs without network access. `tweet-prices` reacquires public quotes; `verify-tweet-prices` additionally checks them against the local raw response cache and repeats the replay with network connections disabled.
