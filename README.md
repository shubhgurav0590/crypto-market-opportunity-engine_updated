# Crypto Market Opportunity Engine

An end-to-end algorithmic trading system for BTC/USDT using 
machine learning and regime-aware signal filtering.

Built from scratch — data pipeline, feature engineering, 
ML model training, backtesting, and live paper trading 
with real-time Telegram alerts.

---

## Live Status
Paper trading since: February 24, 2026
Trades executed: 1 (stop loss, -$100)
Capital: $9,900 / $10,000
System: Running 24/7 on real Binance market data



## How It Works

### Signal Generation Pipeline
Every 5 minutes the system:
1. Fetches 250 candles from Binance API
2. Engineers 19 technical features
3. Applies 6-layer filter stack
4. Runs GradientBoosting ML model
5. Checks signal engine confidence
6. Enters trade or skips

### 6-Layer Filter Stack (in order)
```
Layer 1: EMA50 > EMA200          — trend must be up
Layer 2: EMA200 rising            — not a downtrend month
Layer 3: EMA50 slope > 0.0006    — strongly trending
Layer 4: RSI between 42-72       — not overbought/oversold
Layer 5: Volume ratio > 0.90     — sufficient volume
Layer 6: 3-bar momentum > 0.0002 — positive momentum
Gate  7: ML probability > 0.49   — model confidence
Gate  8: Signal confidence > 0.55 — final quality gate
```

### Risk Management
- Stop loss: -0.25% per trade
- Profit target: +0.35% per trade
- Risk per trade: 1% of capital
- Position size: (capital × 1%) / 0.25%

---

## Project Structure
```
## Results

| Month | Trades | Win Rate | Profit Factor | P&L |
|-------|--------|----------|---------------|-----|
| Jan 2025 | 9  | 55.6% | 1.21 | +$46   |
| Feb 2025 | 11 | 45.5% | 0.51 | -$166  |
| Mar 2025 | 10 | 70.0% | 1.77 | +$130  |
| Apr 2025 | 12 | 58.3% | 1.24 | +$68   |
| May 2025 | 10 | 60.0% | 1.49 | +$110  |
| Jun 2025 | 5  | 60.0% | 1.27 | +$30   |
| Jul 2025 | 6  | 66.7% | 2.29 | +$144  |
| Aug 2025 | 5  | 20.0% | 0.29 | -$160  |
| Sep 2025 | 5  | 60.0% | 1.71 | +$80   |
| Oct 2025 | 11 | 54.5% | 1.26 | +$69   |
| Nov 2025 | 8  | 75.0% | 3.43 | +$272  |
| Dec 2025 | 4  | 50.0% | 1.14 | +$16   |
| **OVERALL** | **101** | **57.4%** | **1.28** | **+$669** |

Starting capital: $100,000
Final capital: $100,669
Return on capital: +0.67%
Best month: Nov 2025 — PF 3.43, 75% WR
Worst month: Aug 2025 — PF 0.29, 20% WR
```


**Your final clean project structure is now:**
```
crypto-market-opportunity-engine/
├── backtest/
│   ├── __init__.py
│   ├── backtest_runner.py    ← fixed, no broken imports
│   └── portfolio.py          ← keep
│   (metrics.py → DELETE)
├── live/
│   ├── __init__.py
│   └── paper_trader.py       ← v4
├── ml/
│   ├── train_momentum_model.py
│   ├── merge_data.py
│   ├── diagnose_data.py
│   ├── fix_columns.py
│   ├── inspect_and_fix_data.py
│   └── clipper.py
├── models/
│   ├── momentum_logistic.pkl
│   ├── momentum_logistic_clip_bounds.pkl
│   └── momentum_logistic_feature_cols.pkl
├── strategy/
│   └── signal_engine.py
├── data/processed/
│   ├── paper_trades.csv
│   ├── signal_log.csv
│   └── trade_log.csv
├
├── research/
│   └── (13 .md files)
├── .env          ← gitignored
├── .gitignore
├── requirements.txt
└── README.md
---

## Tech Stack

| Area | Tools |
|------|-------|
| Language | Python 3.11 |
| Data | Pandas, NumPy |
| ML | Scikit-learn (GradientBoostingClassifier) |
| Exchange API | python-binance |
| Alerts | Telegram Bot API |
| Scheduling | Custom time-based loop |
| Model Storage | Joblib |
| Config | python-dotenv |

---

## ML Model

**Algorithm:** GradientBoostingClassifier
- 300 estimators
- Max depth: 3
- Learning rate: 0.03
- Regime-aligned training (same filters applied during training and deployment)

**Key insight:** Model trained only on samples that passed 
the regime filters — this eliminated distribution mismatch 
between training and live deployment.

**19 Features across 5 categories:**
- Momentum: return_pct, mom_3, mom_6, mom_12
- Volatility: range_pct, range_5bar, vol_compression
- Volume: vol_change, vol_ratio, vol_ratio_5
- Trend: ema_dist, ema_50_dist, ema_9_slope, ema_50_slope
- RSI: rsi_14, rsi_change, rsi_5bar_avg
- Breakout: up_bars_10, dist_from_high

**Top feature by importance:** range_5bar (49%)

---

## Data Pipeline

1. Raw OHLCV data downloaded from Binance (5-minute candles)
2. **Critical data fix:** Diagnosed corrupt source files where 
   close price column contained volume values and candle 
   ranges were zero. Fixed by rebuilding from clean monthly 
   source files and validating OHLC integrity.
3. 12 monthly files merged into single validated dataset
4. 105,000 rows after cleaning

---

## Setup

### Requirements
```bash
pip install -r requirements.txt
```

### Environment Variables
Create a `.env` file:
```
API_Key=your_binance_api_key
Secret_Key=your_binance_secret_key
TELEGRAM_BOT_TOKEN_PROD=your_telegram_bot_token
TELEGRAM_CHAT_ID_PROD=your_telegram_chat_id
```

**Binance API permissions needed:**
- USER_DATA ✓
- USER_STREAM ✓
- TRADE ✗ (never checked — read only)

### Run Paper Trader
```bash
python -m live.paper_trader
```

### Run Backtest
```bash
python -m backtest.backtest_runner
```

---

## Telegram Alerts

The system sends real-time alerts for:
- Startup confirmation with BTC price and config
- Every buy signal fired (ML, RSI, stop/target prices)
- Every trade exit (target hit or stop loss)
- Daily summary at midnight
- Any connection errors with auto-recovery status

---

## Research Documentation

See the `/research` folder for full documentation:
- `problem_statement.md` — why this was built
- `hypotheses.md` — 6 testable hypotheses with validation status
- `experiment_design.md` — how experiments were structured
- `assumptions.md` — explicit research assumptions
- `limitations.md` — honest limitations of the system
- `failure_modes.md` — known failure scenarios and protections
- `non_goals.md` — what this system does not claim to do
- `future_work.md` — roadmap to PF 2.0

---

## Known Limitations

- Single asset (BTC/USDT only)
- 5-minute polling causes stop loss slippage
- Static model (no automatic retraining)
- Runs on laptop (not cloud server yet)
- 109 backtest trades — sufficient but not large sample

Full limitations documented in `research/limitations.md`

---

## Roadmap

**V2 — Multi-asset (Month 2)**
Add ETH and SOL signals for more trade opportunities

**V3 — Multi-timeframe (Month 3)**
15-minute and 1-hour confluence filters

**V4 — Dynamic targets (Month 4)**
Volatility-based profit target scaling

**V5 — Ensemble model + Airflow (Month 5)**
GBM + LSTM ensemble with automated daily retraining

**Target:** PF 2.0+ by end of 2026

---

## Disclaimer

This is a research and paper trading project.
No real money is traded.
This is not financial advice.
Past backtest performance does not guarantee future results.