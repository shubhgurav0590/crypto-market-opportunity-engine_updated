"""
Run this to inspect and fix your raw data.

Usage:
    python -m ml.inspect_and_fix_data
"""

import pandas as pd
import numpy as np

DATA_PATH  = "data/processed/BTCUSDT_5m_clean.parquet"
FIXED_PATH = "data/processed/BTCUSDT_5m_clean.parquet"   # overwrites in place

def inspect_and_fix():
    df = pd.read_parquet(DATA_PATH)

    print("=" * 55)
    print("RAW DATA INSPECTION")
    print("=" * 55)

    print(f"\n📋 Shape        : {df.shape}")
    print(f"📋 Index type   : {type(df.index)}")
    print(f"📋 Columns      : {list(df.columns)}")
    print(f"\n📋 dtypes:\n{df.dtypes}")

    print(f"\n📋 First 5 rows:\n{df.head()}")
    print(f"\n📋 Last 5 rows:\n{df.tail()}")

    print(f"\n📋 open  range : {df['open'].min():.6f}  →  {df['open'].max():.6f}")
    print(f"📋 high  range : {df['high'].min():.6f}  →  {df['high'].max():.6f}")
    print(f"📋 low   range : {df['low'].min():.6f}  →  {df['low'].max():.6f}")
    print(f"📋 close range : {df['close'].min():.6f}  →  {df['close'].max():.6f}")
    print(f"📋 volume range: {df['volume'].min():.2f}  →  {df['volume'].max():.2f}")

    # ── Check ordering ───────────────────────────────────────────────
    print("\n" + "=" * 55)
    print("ORDER CHECK")
    print("=" * 55)

    if "open_time" in df.columns:
        print(f"\n  open_time first : {df['open_time'].iloc[0]}")
        print(f"  open_time last  : {df['open_time'].iloc[-1]}")
        is_ascending = df["open_time"].iloc[0] < df["open_time"].iloc[-1]
        print(f"  Chronological? : {'✅ YES' if is_ascending else '❌ NO — data is REVERSED'}")
    elif hasattr(df.index, "dtype") and "datetime" in str(df.index.dtype):
        is_ascending = df.index[0] < df.index[-1]
        print(f"  Index is datetime. Chronological? : {'✅ YES' if is_ascending else '❌ NO — REVERSED'}")
    else:
        print("  ⚠️  No datetime column found to check order")

    # ── Check if close is scaled / in wrong units ────────────────────
    print("\n" + "=" * 55)
    print("PRICE SANITY CHECK")
    print("=" * 55)

    close_max = df["close"].max()
    if close_max < 100:
        print(f"\n  ⚠️  Max close = {close_max:.4f} — looks like prices may be in wrong units")
        print(f"     (BTC should be in thousands of USD. Could this be ETH, SOL, or a small alt?)")
        print(f"     Or prices might need multiplying by a factor.")
    elif close_max > 100_000:
        print(f"\n  ⚠️  Max close = {close_max:.2f} — very high. Could be in satoshis or wrong pair.")
    else:
        print(f"\n  ✅ Max close = {close_max:.2f} — looks reasonable for BTC/USD")

    # ── Check OHLC integrity ─────────────────────────────────────────
    print("\n" + "=" * 55)
    print("OHLC INTEGRITY CHECK")
    print("=" * 55)

    bad_high = (df["high"] < df["close"]).sum()
    bad_low  = (df["low"]  > df["close"]).sum()
    bad_hl   = (df["high"] < df["low"]).sum()

    print(f"\n  high < close  : {bad_high} rows  {'❌ BAD' if bad_high > 0 else '✅'}")
    print(f"  low  > close  : {bad_low}  rows  {'❌ BAD' if bad_low  > 0 else '✅'}")
    print(f"  high < low    : {bad_hl}   rows  {'❌ BAD' if bad_hl   > 0 else '✅'}")

    sample_range = ((df["high"] - df["low"]) / df["close"] * 100).median()
    print(f"\n  Median candle range : {sample_range:.6f}%")
    if sample_range < 0.001:
        print("  ❌ Near-zero candle ranges — high/low columns are likely WRONG")
        print("     (columns may be swapped, or high==low==close everywhere)")
    elif sample_range < 0.1:
        print("  ⚠️  Very small candle ranges — data may be in wrong units or timeframe")
    else:
        print("  ✅ Candle ranges look normal")

    # ── Attempt auto-fix ─────────────────────────────────────────────
    print("\n" + "=" * 55)
    print("AUTO-FIX")
    print("=" * 55)

    fixed = False

    # Fix 1: sort by time if reversed
    if "open_time" in df.columns:
        df["open_time"] = pd.to_numeric(df["open_time"], errors="coerce")
        if df["open_time"].iloc[0] > df["open_time"].iloc[-1]:
            print("\n  🔧 Sorting by open_time ascending...")
            df = df.sort_values("open_time").reset_index(drop=True)
            fixed = True
            print("     ✅ Done. First timestamp:", df["open_time"].iloc[0],
                  "| Last:", df["open_time"].iloc[-1])

    # Fix 2: convert open_time from milliseconds to datetime if needed
    if "open_time" in df.columns:
        sample_ts = df["open_time"].iloc[0]
        if sample_ts > 1e12:   # milliseconds
            print("\n  🔧 Converting open_time from ms to datetime...")
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
            fixed = True
            print(f"     ✅ First candle: {df['open_time'].iloc[0]}")
            print(f"     ✅ Last  candle: {df['open_time'].iloc[-1]}")

    # Fix 3: set open_time as index
    if "open_time" in df.columns and df.index.dtype != "datetime64[ns]":
        print("\n  🔧 Setting open_time as index...")
        df = df.set_index("open_time")
        fixed = True
        print("     ✅ Done")

    if fixed:
        df.to_parquet(FIXED_PATH)
        print(f"\n  ✅ Fixed data saved to {FIXED_PATH}")
        print(f"  📋 Final shape : {df.shape}")
        print(f"  📋 Close range : {df['close'].min():.4f} → {df['close'].max():.4f}")

        # Recheck candle range after fix
        sample_range_fixed = ((df["high"] - df["low"]) / df["close"] * 100).median()
        print(f"  📋 Median candle range : {sample_range_fixed:.6f}%")
        if sample_range_fixed > 0.01:
            print("  ✅ Candle ranges now look healthy — safe to retrain")
        else:
            print("  ❌ Candle ranges still near zero — OHLC columns may be in wrong format")
            print("     Check if your data source exports high/low correctly")
    else:
        print("\n  ℹ️  No automatic fixes applied.")
        print("  Check the inspection output above and fix the data manually.")

    print("\n" + "=" * 55)
    print("WHAT TO DO NEXT")
    print("=" * 55)
    print("""
  1. Read the inspection output above carefully
  2. Check: is this actually BTC data? (close should be $20k–$100k range)
  3. Check: is open_time sorted oldest → newest?
  4. Check: are high/low columns populated (median range > 0.01%)?
  5. If auto-fix ran, re-run ml.diagnose_data to confirm positive rate is now sane
  6. If still broken, share the output of this script and I can help fix the source data
""")

if __name__ == "__main__":
    inspect_and_fix()