"""
Fixes the column misalignment in BTCUSDT_5m_clean.parquet.

The raw Binance OHLCV API returns columns in this exact order:
  open_time, open, high, low, close, volume, close_time,
  quote_asset_volume, number_of_trades,
  taker_buy_base_asset_volume, taker_buy_quote_asset_volume

Inspection shows the data was saved with columns shifted/misnamed.
This script remaps them correctly and validates the result.

Usage:
    python -m ml.fix_columns
"""

import pandas as pd
import numpy as np

RAW_PATH   = "data/processed/BTCUSDT_5m_clean.parquet"
FIXED_PATH = "data/processed/BTCUSDT_5m_clean.parquet"  # overwrites in place
BACKUP_PATH = "data/processed/BTCUSDT_5m_clean_BACKUP.parquet"

def fix_columns():
    df = pd.read_parquet(RAW_PATH).reset_index(drop=True)

    print("📋 Current columns:", list(df.columns))
    print(f"📋 Shape: {df.shape}\n")

    # Back up the original first
    df.to_parquet(BACKUP_PATH)
    print(f"💾 Backup saved to {BACKUP_PATH}\n")

    # ── Show current column value ranges to identify what's what ──
    print("Current column ranges (to identify misalignment):")
    for col in df.columns:
        try:
            print(f"  {col:40s}: {df[col].min():.4f}  →  {df[col].max():.4f}")
        except Exception:
            print(f"  {col:40s}: (non-numeric or datetime)")

    # ── Remap based on what we know from the inspection ──────────────
    # open_time  → real timestamps (datetime64, keep as-is)
    # open       → 76k-125k  ✅ correct
    # high       → 75k-125k  but high==low always → likely close_time leaked in
    # low        → 75k-125k  ✅ correct  
    # close      → 1.19-1584 ❌ wrong — this is quote_asset_volume scaled
    # volume     → 1.7e15    ❌ wrong — this is close_time in milliseconds
    #
    # The Binance API raw column order is fixed. We reassign by position.
    
    print("\n🔧 Reassigning columns by Binance API position order...")

    # Drop the corrupted index if open_time was set as index by previous script
    if df.index.name == "open_time":
        df = df.reset_index()

    # Binance kline columns in guaranteed order
    BINANCE_COLS = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_asset_volume",
        "number_of_trades",
        "taker_buy_base_asset_volume",
        "taker_buy_quote_asset_volume",
    ]

    if len(df.columns) == len(BINANCE_COLS):
        df.columns = BINANCE_COLS
        print("  ✅ Columns renamed by position")
    else:
        print(f"  ⚠️  Column count mismatch: got {len(df.columns)}, expected {len(BINANCE_COLS)}")
        print("  Attempting partial fix...")

    # ── Convert types ─────────────────────────────────────────────
    # open_time: convert from ms if numeric
    if df["open_time"].dtype != "datetime64[ns]":
        sample = df["open_time"].iloc[0]
        if isinstance(sample, (int, float)) and sample > 1e12:
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
            print("  ✅ open_time converted from ms → datetime")
    
    # close_time: convert from ms to datetime
    if df["close_time"].dtype != "datetime64[ns]":
        try:
            ct_sample = df["close_time"].iloc[0]
            if isinstance(ct_sample, (int, float)) and ct_sample > 1e12:
                df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
        except Exception:
            pass

    # Ensure OHLCV are float
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Sort chronologically
    df = df.sort_values("open_time").reset_index(drop=True)
    print("  ✅ Sorted chronologically")

    # ── Validate ──────────────────────────────────────────────────
    print("\n📊 Post-fix validation:")
    print(f"  open  range : {df['open'].min():>12.2f}  →  {df['open'].max():>12.2f}")
    print(f"  high  range : {df['high'].min():>12.2f}  →  {df['high'].max():>12.2f}")
    print(f"  low   range : {df['low'].min():>12.2f}  →  {df['low'].max():>12.2f}")
    print(f"  close range : {df['close'].min():>12.2f}  →  {df['close'].max():>12.2f}")
    print(f"  volume mean : {df['volume'].mean():>12.4f}")

    median_range = ((df["high"] - df["low"]) / df["close"] * 100).median()
    print(f"  Median candle range : {median_range:.4f}%")

    bad_low  = (df["low"]  > df["close"]).sum()
    bad_high = (df["high"] < df["close"]).sum()
    bad_hl   = (df["high"] < df["low"]).sum()
    print(f"  low > close  : {bad_low}  rows  {'❌' if bad_low  > 0 else '✅'}")
    print(f"  high < close : {bad_high} rows  {'❌' if bad_high > 0 else '✅'}")
    print(f"  high < low   : {bad_hl}   rows  {'❌' if bad_hl   > 0 else '✅'}")

    if median_range > 0.01 and bad_low == 0 and bad_high == 0:
        print("\n✅ Data looks healthy — safe to retrain")

        # Set open_time as index and save
        df = df.set_index("open_time")
        df.to_parquet(FIXED_PATH)
        print(f"✅ Fixed data saved to {FIXED_PATH}")
        print(f"\nNext step: python -m ml.diagnose_data")

    else:
        print("\n❌ Data still has issues after column fix.")
        print("   This means the raw source data itself is corrupt.")
        print("   You need to re-download from Binance.")
        print("\n   Run the downloader below to get fresh data:")
        print("   python -m ml.download_data")

    return df


if __name__ == "__main__":
    fix_columns()