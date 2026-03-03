"""
Merges all monthly BTCUSDT 5m parquet files into one clean dataset.

Detects and uses whichever files are available:
  - BTCUSDT_5m_2025.parquet          (full year if present)
  - BTCUSDT-5m-2025-01.parquet       (monthly files Jan–Dec)
  - BTC_VALIDATION_FRESH.parquet     (your validation set)

Saves:
  - data/processed/BTCUSDT_5m_clean.parquet       ← training data (all 2025)
  - data/processed/BTC_VALIDATION_FRESH.parquet   ← kept separate for backtest

Usage:
    python -m ml.merge_data
"""

import pandas as pd
import numpy as np
import os
import glob

DATA_DIR       = "data/processed"
OUTPUT_TRAIN   = "data/processed/BTCUSDT_5m_clean.parquet"
OUTPUT_VAL     = "data/processed/BTC_VALIDATION_FRESH.parquet"

BINANCE_COLS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_asset_volume", "number_of_trades",
    "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume",
]

def load_and_clean(path):
    """Load a parquet file, fix column names, types, and sort."""
    df = pd.read_parquet(path)

    # Always restore index to column regardless of index name
    # (open_time is often saved as index — we need it as a column)
    if df.index.name is not None or "open_time" not in df.columns:
        df = df.reset_index()

    # If still no open_time, the first column is likely the timestamp
    if "open_time" not in df.columns:
        df.columns = ["open_time"] + list(df.columns[1:])

    # Rename columns by position if they're misnamed
    core_cols = ["open_time", "open", "high", "low", "close", "volume"]
    if not all(c in df.columns for c in core_cols):
        if len(df.columns) >= 11:
            df.columns = BINANCE_COLS[:len(df.columns)]

    # Convert open_time to datetime
    if "open_time" in df.columns:
        col = df["open_time"]
        if col.dtype != "datetime64[ns]":
            sample = col.dropna().iloc[0]
            if isinstance(sample, (int, float)) and sample > 1e12:
                df["open_time"] = pd.to_datetime(col, unit="ms")
            else:
                df["open_time"] = pd.to_datetime(col, errors="coerce")

    # Ensure OHLCV are numeric
    for c in ["open", "high", "low", "close", "volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Keep only needed columns
    keep = [c for c in BINANCE_COLS if c in df.columns]
    df = df[keep]

    df = df.dropna(subset=[c for c in ["open_time", "open", "high", "low", "close"] if c in df.columns])
    df = df.sort_values("open_time").reset_index(drop=True)
    return df


def validate(df, label=""):
    """Print a health summary for a DataFrame."""
    median_range = ((df["high"] - df["low"]) / df["close"] * 100).median()
    bad_hl = (df["high"] < df["low"]).sum()
    bad_lc = (df["low"] > df["close"]).sum()
    bad_hc = (df["high"] < df["close"]).sum()

    print(f"\n{'─'*50}")
    print(f"  {label}")
    print(f"{'─'*50}")
    print(f"  Rows              : {len(df):,}")
    print(f"  Date range        : {df['open_time'].iloc[0].date()}  →  {df['open_time'].iloc[-1].date()}")
    print(f"  Close range       : ${df['close'].min():>10,.2f}  →  ${df['close'].max():>10,.2f}")
    print(f"  Median candle rng : {median_range:.4f}%  {'✅' if median_range > 0.01 else '❌ near zero'}")
    print(f"  OHLC integrity    : {'✅ OK' if bad_hl + bad_lc + bad_hc == 0 else f'❌ {bad_hl+bad_lc+bad_hc} bad rows'}")
    return median_range > 0.01 and bad_hl == 0


def merge_data():
    print("🔍 Scanning data/processed for available files...\n")

    # ── Discover monthly files ────────────────────────────────────
    monthly_files = sorted(glob.glob(f"{DATA_DIR}/BTCUSDT-5m-2025-*.parquet"))
    full_year     = f"{DATA_DIR}/BTCUSDT_5m_2025.parquet"
    val_file      = f"{DATA_DIR}/BTC_VALIDATION_FRESH.parquet"

    print(f"  Full year file   : {'✅ found' if os.path.exists(full_year) else '❌ not found'}  ({full_year})")
    print(f"  Monthly files    : {len(monthly_files)} found")
    for f in monthly_files:
        print(f"    {os.path.basename(f)}")
    print(f"  Validation file  : {'✅ found' if os.path.exists(val_file) else '❌ not found'}  ({val_file})")

    # ── Choose source ─────────────────────────────────────────────
    frames = []

    if os.path.exists(full_year):
        print(f"\n📂 Loading full year file: {full_year}")
        frames.append(load_and_clean(full_year))
    elif monthly_files:
        print(f"\n📂 Loading {len(monthly_files)} monthly files...")
        for path in monthly_files:
            df_m = load_and_clean(path)
            frames.append(df_m)
            print(f"  ✅ {os.path.basename(path):35s}  {len(df_m):,} rows  "
                  f"{df_m['open_time'].iloc[0].date()} → {df_m['open_time'].iloc[-1].date()}")
    else:
        print("\n❌ No training data files found.")
        print("   Expected either BTCUSDT_5m_2025.parquet or BTCUSDT-5m-2025-XX.parquet files.")
        return

    # ── Merge ─────────────────────────────────────────────────────
    train_df = pd.concat(frames, ignore_index=True)
    train_df = train_df.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)

    # ── Validate training data ────────────────────────────────────
    ok = validate(train_df, "TRAINING DATA (merged)")

    if not ok:
        print("\n⚠️  Training data has integrity issues even after merge.")
        print("   The source files themselves may have corrupt OHLC data.")
        print("   Try running: python -m ml.download_data")
        return

    # ── Save training data ────────────────────────────────────────
    train_df.set_index("open_time").to_parquet(OUTPUT_TRAIN)
    print(f"\n✅ Training data saved → {OUTPUT_TRAIN}")
    print(f"   {len(train_df):,} rows ready for training")

    # ── Validate validation file (don't modify it) ────────────────
    if os.path.exists(val_file):
        val_df = load_and_clean(val_file)
        validate(val_df, "VALIDATION DATA (backtest)")
        print(f"\n✅ Validation file looks good — no changes made to {val_file}")

    # ── Summary ───────────────────────────────────────────────────
    print(f"""
{'='*50}
✅ DONE — Next steps:
{'='*50}
  1. Confirm data looks healthy above
  2. python -m ml.diagnose_data          ← check positive rate
  3. python -m ml.train_momentum_model   ← retrain model
  4. python -m backtest.backtest_runner  ← run backtest
""")


if __name__ == "__main__":
    merge_data()