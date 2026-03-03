# Feature Freeze — v2.0 (Production)

This document locks the feature set used in the production
paper trading system.

Previous v1.0 is superseded by this document.

## Final Feature Set (19 Features)

### Momentum Features
- return_pct     — single candle return (close-open)/open
- mom_3          — 3-bar price change
- mom_6          — 6-bar price change
- mom_12         — 12-bar price change

### Volatility Features
- range_pct      — candle range (high-low)/close
- range_5bar     — 5-bar average range
- vol_compression — current range vs 20-bar average range

### Volume Features
- vol_change     — volume change vs previous candle
- vol_ratio      — volume vs 20-bar average
- vol_ratio_5    — volume vs 5-bar average

### Trend Features
- ema_dist       — distance from EMA9
- ema_50_dist    — distance from EMA50
- ema_9_slope    — EMA9 slope over 3 bars
- ema_50_slope   — EMA50 slope over 10 bars

### RSI Features
- rsi_14         — 14-period RSI (Wilder method)
- rsi_change     — RSI change vs previous bar
- rsi_5bar_avg   — 5-bar RSI average

### Breakout Context Features
- up_bars_10     — ratio of up candles in last 10 bars
- dist_from_high — distance from 20-bar high

## Removed from v1.0
- Hour of day    — removed, not predictive in validation
- Day of week    — removed, not predictive in validation
- taker_buy_quote_asset_volume — constant, removed
- range (raw)    — replaced by range_pct

## Feature Importance (Top 5 from GBM)
1. range_5bar        — 49% importance
2. vol_compression
3. ema_50_slope
4. rsi_14
5. mom_3

## Rules
Any new feature requires:
- sanity checks (no NaN, no inf)
- leakage tests (no future data)
- backtest validation before deployment
- version bump in this document