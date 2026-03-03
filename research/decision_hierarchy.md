# Decision Hierarchy & Override Rules

This document defines how decisions are prioritized when signals or components disagree.

## Core Principle
Safety always overrides opportunity.

## Decision Priority (Highest to Lowest)

1. Kill Switch
   - Triggered by system failure, extreme market stress, or data issues.
   - Immediately stops all trading activity.

2. Risk Intelligence Layer
   - Detects market stress, uncertainty, and instability.
   - Can reduce risk, suppress trades, or halt trading.

3. Behavioral Safety Layer
   - Prevents overtrading, revenge trading, and loss spirals.
   - Enforces cooldowns and risk reduction.

4. Market Regime Logic
   - Adjusts strategy behavior based on regime.
   - Limits trading in sideways or unstable regimes.

5. Strategy Rules
   - Applies trade filters and confidence gating.

6. Machine Learning Models
   - Generate directional signals only.
   - Never execute trades independently.

## Important Rules
- “Do nothing” is a valid and preferred decision during high risk.
- No lower layer can override a higher layer.
- Execution only happens if all higher-priority layers allow it.

This hierarchy ensures predictable, safe, and explainable system behavior.
