"""
Run this BEFORE training to understand your data's actual movement distribution.
This tells us exactly what TARGET_UP and TARGET_DOWN values will give a balanced label.

Usage:
    python -m ml.diagnose_data
"""

import pandas as pd
import numpy as np
from features.indicators import ema, rsi

DATA_PATH      = "data/processed/BTCUSDT_5m_clean.parquet"
LOOKAHEAD_BARS = 24

def diagnose():
    df = pd.read_parquet(DATA_PATH).reset_index(drop=True)

    print(f"📦 Total rows     : {len(df)}")
    print(f"📅 Date range     : {df.index[0]} → {df.index[-1]}" if hasattr(df.index, 'date') else f"📅 Rows 0 → {len(df)-1}")
    print(f"💰 Close range    : {df['close'].min():.2f} → {df['close'].max():.2f}")
    print(f"📊 Columns        : {list(df.columns)}\n")

    # ── Candle-level stats ──────────────────────────────────────────
    df["candle_range"] = (df["high"] - df["low"]) / df["close"] * 100
    df["return_pct"]   = (df["close"] - df["open"]) / df["open"] * 100

    print("── Per-candle movement (%) ──────────────────────────")
    print(f"  Candle range  mean : {df['candle_range'].mean():.4f}%")
    print(f"  Candle range  p50  : {df['candle_range'].median():.4f}%")
    print(f"  Candle range  p95  : {df['candle_range'].quantile(0.95):.4f}%")
    print(f"  Candle range  p99  : {df['candle_range'].quantile(0.99):.4f}%")
    print(f"  Return pct    mean : {df['return_pct'].mean():.4f}%")
    print(f"  Return pct    std  : {df['return_pct'].std():.4f}%\n")

    # ── Max excursion over LOOKAHEAD window ─────────────────────────
    closes = df["close"].values
    highs  = df["high"].values
    lows   = df["low"].values
    n      = len(df)

    max_up   = np.zeros(n)
    max_down = np.zeros(n)

    print(f"⏳ Computing max excursions over {LOOKAHEAD_BARS} bars... ", end="", flush=True)
    for i in range(n):
        end    = min(i + 1 + LOOKAHEAD_BARS, n)
        entry  = closes[i]
        window_highs = highs[i+1:end]
        window_lows  = lows[i+1:end]
        if len(window_highs) == 0:
            continue
        max_up[i]   = (window_highs.max() - entry) / entry * 100
        max_down[i] = (entry - window_lows.min())  / entry * 100   # positive = how far it dropped
    print("done\n")

    print(f"── Max UP move in next {LOOKAHEAD_BARS} bars (%) ────────────────────")
    for p in [25, 50, 75, 90, 95, 99]:
        print(f"  p{p:2d} : {np.percentile(max_up, p):.4f}%")

    print(f"\n── Max DOWN move in next {LOOKAHEAD_BARS} bars (%) ──────────────────")
    for p in [25, 50, 75, 90, 95, 99]:
        print(f"  p{p:2d} : {np.percentile(max_down, p):.4f}%")

    # ── Simulate positive rates at various thresholds ───────────────
    print("\n── Simulated Positive Rate (path-dependent) ─────────────")
    print(f"  {'TARGET_UP':>10}  {'TARGET_DOWN':>12}  {'Positive Rate':>14}")
    print(f"  {'-'*10}  {'-'*12}  {'-'*14}")

    test_pairs = [
        (0.5,  0.3), (0.8,  0.4), (1.0,  0.5),
        (1.2,  0.5), (1.5,  0.5), (1.5,  0.6),
        (2.0,  0.6), (2.0,  1.0), (3.0,  1.0),
    ]

    for up_pct, down_pct in test_pairs:
        up   = up_pct   / 100
        down = down_pct / 100
        hits = 0
        for i in range(n):
            end   = min(i + 1 + LOOKAHEAD_BARS, n)
            entry = closes[i]
            hit   = 0
            for j in range(i + 1, end):
                if (lows[j]  - entry) / entry <= -down: hit = 0; break
                if (highs[j] - entry) / entry >=  up:   hit = 1; break
            hits += hit
        rate = hits / n * 100
        marker = " ✅ good" if 30 <= rate <= 50 else (" ⚠️  high" if rate > 50 else " ⚠️  low")
        print(f"  {up_pct:>9.1f}%  {down_pct:>11.1f}%  {rate:>13.2f}%{marker}")

    print("\n✅ Use the TARGET_UP / TARGET_DOWN pair with rate closest to 35-45%")
    print("   Update those values in train_model.py and retrain.\n")

if __name__ == "__main__":
    diagnose()