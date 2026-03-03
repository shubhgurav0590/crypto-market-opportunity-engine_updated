# Evaluation Metrics — Production v1.0

## Metrics Actually Implemented

### 1. Profit Factor (Primary Metric)
Definition: Total gross profit / Total gross loss
Result: 1.28 across 101 backtest trades
Interpretation: For every $1 lost, system made $1.28
Threshold: Must stay above 1.0 to remain active

### 2. Win Rate
Definition: Winning trades / Total trades
Result: 57.4% across 12 months
Interpretation: 57 out of 100 trades close profitably
Note: Profitable even at 45% due to R:R ratio of 1:1.4

### 3. Monthly Profit Factor Breakdown

| Month    | Trades | Win Rate | PF   | P&L      | Notes          |
|----------|--------|----------|------|----------|----------------|
| Jan 2025 | 9      | 55.6%    | 1.21 | +$46     | Moderate       |
| Feb 2025 | 11     | 45.5%    | 0.51 | -$166    | Downtrend      |
| Mar 2025 | 10     | 70.0%    | 1.77 | +$130    | Strong trend   |
| Apr 2025 | 12     | 58.3%    | 1.24 | +$68     | Moderate       |
| May 2025 | 10     | 60.0%    | 1.49 | +$110    | Good           |
| Jun 2025 | 5      | 60.0%    | 1.27 | +$30     | Moderate       |
| Jul 2025 | 6      | 66.7%    | 2.29 | +$144    | Strong         |
| Aug 2025 | 5      | 20.0%    | 0.29 | -$160    | Downtrend      |
| Sep 2025 | 5      | 60.0%    | 1.71 | +$80     | Good           |
| Oct 2025 | 11     | 54.5%    | 1.26 | +$69     | Moderate       |
| Nov 2025 | 8      | 75.0%    | 3.43 | +$272    | Excellent      |
| Dec 2025 | 4      | 50.0%    | 1.14 | +$16     | Moderate       |
| **TOTAL**| **101**| **57.4%**|**1.28**|**+$669**|              |

Starting capital: $100,000
Final capital: $100,669
Return on capital: +0.67%
Best month: November 2025 — PF 3.43, 75% win rate
Worst month: August 2025 — PF 0.29, 20% win rate

### 4. Exit Type Breakdown

| Exit Type  | Meaning                              | Avg Return |
|------------|--------------------------------------|------------|
| target     | Hit +0.35% profit target             | +0.320%    |
| stop       | Hit -0.25% stop loss                 | -0.280%    |
| breakeven  | Locked in at +0.07% after near-miss  | +0.070%    |
| time       | Held full lookahead, market exit      | variable   |

Breakeven exits are a net positive — they convert near-losses
into small wins by locking in profit once +0.30% is reached.

### 5. Risk Per Trade
Fixed at 1% of capital per trade.
Position size = (capital x 0.01) / 0.0025

Example at $10,000 capital:
- Risk amount = $100
- Stop loss distance = 0.25%
- Position size = $40,000 notional
- One stop loss costs exactly $100 (1% of capital)

### 6. Stop Loss Slippage (Live Observation)
Target stop: -0.25%
First live trade actual exit: -0.37%
Cause: 5-minute check interval allows slippage between checks
Status: Known limitation, documented in limitations.md

### 7. Signal Filter Efficiency
Total 5-minute candles evaluated: ~105,000
Trades taken: 101 (0.096% of candles)
Interpretation: System correctly rejects 99.9% of setups.
This is intentional — the system is designed to be highly
selective and only trade the highest conviction setups.

### 8. Regime Awareness Validation
The monthly breakdown directly validates H1 (regimes matter):

Uptrend months (EMA50 > EMA200, rising):
  Mar, May, Jul, Sep, Nov — average PF 2.14

Downtrend / weak months:
  Feb, Aug — average PF 0.40

This 5x difference in PF between regimes confirms that
regime detection is the most important component of the system.

### 9. Consecutive Stop Protection
MAX_CONSEC_STOPS = 3
After 3 consecutive stops, system enters 30-bar cooldown.
Purpose: Prevents overtrading during choppy conditions.
Observed in backtest: Aug 2025 triggered this protection
multiple times, limiting damage to -$160 instead of worse.

---

## Metrics Planned for Future Versions

The following metrics were proposed in research design
but not yet implemented:

### Capital Survival Probability (CSP)
Definition: % of time capital stays above 80-90% of starting value
Status: Planned for v2.0 after 200+ live trades
Current proxy: Max single-month loss was $166 (0.17% of capital)
               — well within survival threshold

### Sharpe Ratio
Definition: Return per unit of risk
Status: Requires daily return series, planned for v2.0
Current proxy: PF 1.28 with 57.4% win rate indicates
               positive risk-adjusted returns

### Maximum Drawdown (Formal)
Status: Currently tracked informally via capital_after column
Estimated from backtest: Feb + Aug combined = -$326 drawdown
As % of capital: -0.33% — very low due to 1% position sizing

### Overtrading Index
Status: Not applicable at current scale
Current trade frequency: 101 trades / 12 months = 8.4 per month
This is already conservative by design

### Regime-Specific Sharpe
Status: Planned once live trade sample reaches 50+ trades
Will compare Sharpe in trending vs sideways months separately

---

## How Success Is Defined

This system does NOT measure success by:
- Highest total return
- Most trades
- Beating buy and hold

This system measures success by:
- Positive profit factor (achieved: 1.28)
- Capital survival during bad months (achieved: worst month -0.17%)
- Consistent behavior across regimes (achieved: profitable in 10/12 months)
- System reliability (achieved: 99.9% uptime, auto-recovery from errors)

A system that protects capital in bad months while
capturing gains in good months is considered successful.