📄 Research Hypotheses (Simple & Clear)
Why we need hypotheses

A hypothesis is a clear statement we can test with data.

Not:
❌ “This system will work well”

But:
✅ “If we do X, then Y should improve, compared to Z”

If a hypothesis fails, that’s still good research.

H1 — Market conditions matter
Hypothesis

A trading system performs very differently under different market conditions (trending, sideways, highly volatile).

What this means in simple words

Markets don’t behave the same all the time.
A strategy that works in a calm market may fail badly in a chaotic one.

How we will test it

Split historical BTC data into market regimes

Measure performance separately in each regime

Compare drawdowns and losses across regimes

Why this matters

If this is true, then one single model is dangerous.

H2 — Risk control is more important than prediction accuracy
Hypothesis

Adding risk controls (position sizing, trade filters, stop rules) reduces losses more effectively than improving prediction accuracy alone.

In simple words

Even a “smart” prediction can lose money if risk is not controlled.

How we will test it

Compare:

Raw ML predictions

ML + risk filters

Measure:

Max loss

Drawdown

Capital survival

Why this matters

This proves that discipline beats intelligence in markets.

H3 — Knowing when NOT to trade improves survival
Hypothesis

Actively stopping or reducing trading during high-risk periods improves long-term capital survival.

In simple words

Sometimes the best trade is no trade.

How we will test it

Identify high-risk periods using market stress signals

Compare:

Always-trading system

Risk-aware stop-trading system

Measure capital loss during crashes

Why this matters

This directly helps small investors avoid big losses.

H4 — Uncertainty awareness reduces damage
Hypothesis

When the system is uncertain or models disagree, reducing trade size or skipping trades lowers drawdowns.

In simple words

If the system is confused, it should act carefully — not confidently.

How we will test it

Measure model confidence and disagreement

Apply smaller trades or no trades during high uncertainty

Compare drawdowns with normal trading

Why this matters

This prevents overconfidence during dangerous markets.

H5 — Capital survival is a better success measure than profit
Hypothesis

Measuring success using capital survival shows system quality better than profit or accuracy alone.

In simple words

A system that makes money but wipes out users later is a bad system.

How we will test it

Define a Capital Survival metric

Compare strategies with similar profits

See which one protects money better over time

Why this matters

This aligns the system with real people, not gambling.

H6 — Simple, guided automation helps users more than full automation
Hypothesis

Assisted or guarded automation leads to better outcomes than full automatic trading for small investors.

In simple words

Giving users some control and protection is safer than full auto-trading.

How we will test it

Compare:

Paper trading

Assisted auto-trading

Fully automatic trading

Measure losses, overtrading, and recovery

Why this matters

This supports ethical automation.

One-line summary (important)

This research tests whether protecting money and reducing risk leads to better long-term outcomes than chasing high profits in crypto markets.



## Hypothesis Status Update (March 2026)

H1 — Market conditions matter
Status: VALIDATED
Evidence: Feb PF 0.25 vs Nov PF 9.14 on same system.
Regime filters reduced losses in downtrend months.

H2 — Risk control > prediction accuracy
Status: VALIDATED
Evidence: Raw ML alone gave poor results.
Adding 6-layer filter stack raised PF from ~0.9 to 1.34.

H3 — Knowing when NOT to trade improves survival
Status: VALIDATED
Evidence: System skips 99.9% of candles.
EMA50 < EMA200 filter alone blocked entire Feb/Aug periods.

H4 — Uncertainty awareness reduces damage
Status: VALIDATED
Evidence: Confidence threshold 0.55 blocked 4 near-signals
in first live session that would likely have been losses
(BTC was in declining regime during those signals).

H5 — Capital survival is a better success measure than profit
Status: PARTIALLY VALIDATED
Evidence: System prioritizes capital protection over profit.
Formal Capital Survival Probability metric not yet calculated.
Planned for v2.0 after 50+ live trades.

H6 — Guided automation helps users more than full automation
Status: NOT YET TESTED
Evidence: Only one system configuration was built and tested.
Formal comparison between assisted and full automation
requires additional implementation.
Planned as future research direction.