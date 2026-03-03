print("✅ signal_engine.py LOADED (PRODUCTION)")

# ---- ML warning throttle ----
ML_WARNING_SHOWN = False

def momentum_score(return_pct):
    """
    Monotonic momentum scoring with exhaustion protection.
    """
    if return_pct <= 0:
        return 0.0

    # Exhaustion filter (Protection against blow-off tops)
    if return_pct > 0.01:
        return 0.1

    # Ideal momentum zone (Targets the meat of the move)
    if 0.0015 <= return_pct <= 0.004:
        return min(return_pct / 0.004, 1.0)

    # Weak momentum (Provides a baseline floor)
    return max(return_pct / 0.006, 0.2)

def generate_signal(return_pct, close_price, ema_9, rsi_14, ml_proba=None, range_pct=None):

    if return_pct is None or rsi_14 is None:
        return None, 0.0

    # Breakout-friendly RSI
    if not (40 <= rsi_14 <= 78):
        return None, 0.0

    if return_pct <= 0:
        return None, 0.0

    # ML veto aligned with observed distribution
    if ml_proba is not None and ml_proba < 0.16:
        return None, 0.0

    rule_score = momentum_score(return_pct)

    # ML-forward weighting
    confidence = (0.55 * ml_proba) + (0.45 * rule_score)

    return "BUY", confidence
