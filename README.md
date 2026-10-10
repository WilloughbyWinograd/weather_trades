# weather_trades

Compare Global Forecast System (GFS) and High-Resolution Rapid Refresh (HRRR) forecasts for simulated Kalshi temperature trades.

**Status:** Implementation plan published. No backtest has run. No trading account, deposit, or trading credentials are required for the initial research.

[Read the implementation plan](docs/implementation-plan.md).

## Scope

- Discover every city represented in Kalshi's available weather-market data, including historical series and aliases.
- Identify each temperature contract's settlement station and use verified station latitude and longitude.
- Compare GFS and HRRR on identical city, station, date, and decision-time samples where both models have coverage.
- Show all remaining cities and data gaps explicitly, including international cities outside HRRR coverage.
- Estimate simulated returns after fees and execution assumptions. Separately measure forecast accuracy.

## Spending and execution

This project is research only. Do not place real orders, deposit money, purchase data, or create paid infrastructure. Do not add trading credentials or live order-submission code. Use free sources and the existing environment within its current resources. Report any access or cost blocker before proceeding.

The published plan defines future implementation. This repository currently contains documentation only.
