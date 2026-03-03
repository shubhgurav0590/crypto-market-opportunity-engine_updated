# Research Limitations

These limitations are stated transparently.
A system that knows how it fails is more trustworthy
than one that only reports when it wins.

## 1. Single Asset
Built and validated on BTC/USDT only.
Results may not generalize to other assets without
full revalidation including feature engineering,
model retraining, and parameter tuning.

## 2. 12-Month Backtest Window
Covers approximately 105,000 5-minute candles from 2025.
Does not include previous bull/bear full cycles (2021-2024).
A longer history would provide stronger statistical confidence.

## 3. Stop Loss Slippage
The system checks conditions every 5 minutes, not tick-by-tick.
Stop losses can slip beyond the -0.25% target during fast moves.
First live trade: target -0.25%, actual exit -0.37%.
This is a known structural limitation of 5-minute polling.

## 4. Static ML Model
The GradientBoosting model is trained once on 2025 data.
It is never automatically retrained.
As market conditions evolve, model performance may degrade.
Automated daily retraining with Airflow is planned for v2.0.

## 5. Small Live Trade Sample
109 backtest trades is sufficient for initial validation.
However, 1 live trade (as of March 2026) is statistically
insufficient to confirm live performance matches backtest.
A minimum of 50-100 live trades is required for confidence.

## 6. Metrics Gap
Research design proposed Capital Survival Probability,
Sharpe Ratio, and Overtrading Index.
Production system currently measures Profit Factor and
Win Rate only. Formal CSP calculation is future work.

## 7. No Formal Baseline Comparison
Research design proposed comparison against:
- Buy and Hold strategy
- Rule-based technical indicator strategy
This comparison was not formally implemented.
Informally, Buy and Hold BTC in 2025 returned approximately
+40%, while this system returned +0.83% on $100k due to
conservative position sizing (1% risk per trade).
The system is not designed to compete with Buy and Hold —
it is designed to protect capital with controlled risk.

## 8. Regime Detection Lag
EMA-based regime detection inherently lags price action.
During sudden reversals, the system may take 5-15 candles
to detect the regime change.
This caused the first live trade loss — BTC reversed sharply
after entry before the regime filter could block the signal.

## 9. Feature Freeze Outdated at v1.0
Feature freeze document described 9 features from v1.
Production system uses 19 engineered features.
Document updated to v2.0 to reflect actual implementation.

## 10. Laptop Deployment
Current system runs on a personal laptop.
Requires manual uptime management.
Internet drops cause temporary disconnections (auto-recovered).
24/7 reliability requires cloud server deployment (planned).

## 11. February and August Weakness
Despite EMA200 declining filter, these months remain weak.
PF 0.25 in Feb and PF 0.35 in Aug.
The filter reduced trades in these months but did not
eliminate losses entirely.
Stronger regime filters are identified as future work.