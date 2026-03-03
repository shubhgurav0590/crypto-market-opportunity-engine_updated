📄 Experiment Design (Simple & Clear)
1. Goal of the experiments

The goal of these experiments is not to find the most profitable strategy.

The goal is to test whether:

risk-aware decisions

regime awareness

uncertainty handling

controlled automation

can protect capital better than traditional ML-based trading approaches.

All experiments are designed to answer the hypotheses defined earlier.

2. Data selection and preparation
2.1 Asset selection

Primary asset: Bitcoin (BTC)

Reason:

Most liquid crypto asset

Long historical data available

Represents overall crypto market behavior

2.2 Time period

Use multiple years of historical data (5–10 years if available)

Purpose:

Capture bull markets

Bear markets

Sideways markets

Extreme volatility periods

2.3 Era-based split (very important)

Instead of treating all data as one block, split it into eras:

Early market phase

High-growth / bull phase

Crash / bear phase

Recovery / unstable phase

Each era is evaluated separately.

This prevents misleading conclusions.

3. Market regime identification

Market conditions are classified into regimes such as:

Trending market

Sideways / ranging market

Highly volatile / unstable market

Regimes are identified using:

Volatility measures

Trend strength

Price movement consistency

No future information is used (to avoid data leakage).

4. System configurations to compare

To test hypotheses properly, multiple systems are compared.

4.1 Baseline systems

Buy & Hold

No ML

No trading logic

Used as a reference

Rule-based strategy

Technical indicators only

Fixed rules

No ML

4.2 ML-based systems

Raw ML system

ML predictions only

Trades executed without risk controls

ML + Risk Control system

Position sizing

Stop-loss

Trade filters

Risk Guardian system (proposed)

Regime awareness

Uncertainty detection

Market stress detection

Trade suppression during risky periods

5. Trading and execution rules

All systems follow consistent execution rules:

Fixed maximum risk per trade

No leverage (default)

Transaction costs included

Slippage assumptions applied

This ensures fair comparison.

6. Experiment structure

Each experiment follows this flow:

Select data period

Identify market regimes

Generate signals

Apply risk and decision logic

Simulate trades (paper trading)

Record results

Evaluate metrics

This process is repeated for:

Different eras

Different market regimes

Different system configurations

7. Hypothesis-to-experiment mapping
Hypothesis	Tested By
H1	Performance comparison across regimes
H2	ML vs ML + risk control
H3	Trading vs trade suppression
H4	Normal trading vs uncertainty-aware trading
H5	Profit metrics vs capital survival metrics
H6	Assisted vs full automation simulations

This keeps the research structured and traceable.

8. Stress testing and failure scenarios

Special experiments are run during:

Market crashes

Sudden volatility spikes

Long sideways markets

The goal is to observe:

Maximum drawdown

Recovery time

Capital survival rate

Failure is documented, not hidden.

9. Evaluation approach

Results are evaluated using:

Risk-adjusted metrics

Drawdown analysis

Capital survival probability

Stability across regimes

Profit alone is never treated as success.

10. Reproducibility and transparency

To ensure reliability:

All parameters are logged

All experiments are repeatable

No manual tuning per era

Clear documentation of assumptions

This makes the research trustworthy.

11. Expected outcome (honest)

The expected outcome is not perfect performance.

Instead, we expect to show that:

Risk-aware systems lose less during bad times

Capital survives longer

Users are better protected

Profits may be lower but more stable

This supports the core research objective.

One-line summary (very important)

These experiments test whether disciplined, risk-aware decision systems protect users better than aggressive prediction-based trading.

## 12. Actual Implementation vs Design

This section documents where the final implementation
differs from the original experiment design.

### Implemented as designed
- Era-based evaluation (12 months tested individually)
- Regime identification using EMA indicators
- Transaction costs included (0.06% per trade)
- No future information used (walk-forward validation)
- Paper trading phase before live deployment
- Failure documentation (see failure_modes.md)

### Not yet implemented
- Formal Buy & Hold baseline comparison
- Rule-based vs ML formal comparison
- Multiple system configuration comparison
  (Raw ML vs ML + Risk vs Full System)
- Capital Survival Probability metric
- Sharpe Ratio calculation

### Modified from design
- Feature set expanded from 9 to 19 features
- Hour/Day features removed (not predictive)
- Regime detection uses EMA-based rules
  (not ML-based classification as originally planned)

These gaps are acknowledged and planned for v2.0
after 30-day paper trading validation completes.


