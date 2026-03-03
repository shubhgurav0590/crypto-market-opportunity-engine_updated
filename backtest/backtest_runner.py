import pandas as pd
import joblib
import numpy as np
import os
import glob

from strategy.signal_engine import generate_signal
from backtest.portfolio import Portfolio

# ============================================================
# CONFIGURATION — PRODUCTION v8 (Phase 1 + Phase 2)
# ============================================================
MODEL_PATH = "models/momentum_logistic.pkl"
LOG_PATH   = "data/processed/trade_log.csv"

RUN_ALL_MONTHS = True
MONTHLY_GLOB   = "data/processed/BTCUSDT-5m-2025-*.parquet"

CONFIDENCE_THRESHOLD = 0.55
COSTS                = 0.0006
WARMUP_PERIOD        = 220
LOOKAHEAD            = 36

# RISK MANAGEMENT
STOP_LOSS         = -0.0025
PROFIT_TARGET     =  0.0035
BREAKOUT_LOOKBACK =  2
MIN_RANGE_PCT     =  0.0012
BREAKEVEN_TRIGGER =  0.003
BREAKEVEN_LOCK    =  0.001
COOLDOWN_BARS     =  5

# PHASE 2: POSITION SIZING
# Risk exactly 1% of current capital per trade.
# Position size = (capital x risk%) / stop_loss_distance
# One stop loss costs exactly 1% of account — survivable.
INITIAL_CAPITAL  = 100_000
RISK_PER_TRADE   = 0.01      # 1% of capital risked per trade
MAX_POSITION_PCT = 0.20      # never put more than 20% of capital in one trade

# REGIME FILTER
REGIME_LOOKBACK   = 20
REGIME_MIN_SLOPE  = 0.0006
REGIME_MIN_MARGIN = 0.0015

# PHASE 1: EMA200 DECLINING FILTER
# If EMA200 is falling over last 50 bars, BTC is in downtrend.
# Skip all trades — blocks Feb and Aug type months.
EMA200_LOOKBACK = 50

# ENTRY QUALITY FILTERS
RSI_MIN        = 42
RSI_MAX        = 72
MIN_VOL_RATIO  = 0.90
MIN_MOM_3      = 0.0002

# CONSECUTIVE STOP PROTECTION
MAX_CONSEC_STOPS = 3
CHOP_COOLDOWN    = 30
ML_GATE          = 0.49

FEATURE_COLS = [
    "return_pct", "range_pct", "vol_change",
    "ema_dist", "ema_50_dist",
    "vol_ratio", "vol_ratio_5",
    "rsi_14", "rsi_change", "rsi_5bar_avg",
    "mom_3", "mom_6", "mom_12",
    "range_5bar", "vol_compression",
    "up_bars_10", "dist_from_high",
    "ema_9_slope", "ema_50_slope",
]


# ============================================================
# FEATURE HELPERS — inlined to remove features/ dependency
# ============================================================

def ema(series, span=9):
    return series.ewm(span=span, adjust=False).mean()


def rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    return 100 - (100 / (1 + gain / loss.replace(0, 1e-10)))


# ============================================================
# FEATURE ENGINEERING — must match paper_trader.py exactly
# ============================================================

def compute_features(df):
    df = df.copy()
    df["return_pct"]  = (df["close"] - df["open"]) / df["open"]
    df["range_pct"]   = (df["high"] - df["low"]) / df["close"]
    df["vol_change"]  = df["volume"].pct_change().replace([np.inf, -np.inf], np.nan)
    df["ema_9"]       = ema(df["close"], span=9)
    df["ema_50"]      = ema(df["close"], span=50)
    df["ema_200"]     = ema(df["close"], span=200)
    df["rsi_14"]      = rsi(df["close"], period=14)
    df["ema_dist"]    = (df["close"] - df["ema_9"])  / df["ema_9"]
    df["ema_50_dist"] = (df["close"] - df["ema_50"]) / df["ema_50"]
    df["vol_ratio"]      = df["volume"] / df["volume"].rolling(20).mean()
    df["vol_ratio_5"]    = df["volume"] / df["volume"].rolling(5).mean()
    df["rsi_change"]     = df["rsi_14"].diff()
    df["rsi_5bar_avg"]   = df["rsi_14"].rolling(5).mean()
    df["mom_3"]          = df["close"].pct_change(3)
    df["mom_6"]          = df["close"].pct_change(6)
    df["mom_12"]         = df["close"].pct_change(12)
    df["range_5bar"]      = df["range_pct"].rolling(5).mean()
    df["vol_compression"] = df["range_pct"] / (df["range_pct"].rolling(20).mean() + 1e-10)
    df["up_bars_10"]      = (df["close"] > df["open"]).rolling(10).sum() / 10
    df["high_20"]         = df["high"].rolling(20).max()
    df["dist_from_high"]  = (df["close"] - df["high_20"]) / (df["high_20"] + 1e-10)
    df["ema_9_slope"]     = df["ema_9"].pct_change(3)
    df["ema_50_slope"]    = df["ema_50"].pct_change(10)
    return df


# ============================================================
# BACKTEST ENGINE
# ============================================================

def run_backtest(ml_model, data_path, label=""):
    if not os.path.exists(data_path):
        print(f"Missing: {data_path}")
        return None

    df = pd.read_parquet(data_path)
    if df.index.name == "open_time":
        df = df.reset_index()
    df = df.reset_index(drop=True)
    df = compute_features(df)

    capital      = float(INITIAL_CAPITAL)
    portfolio    = Portfolio(initial_capital=INITIAL_CAPITAL)
    trades       = 0
    skip_until   = 0
    ml_probs     = []
    trade_log    = []
    consec_stops = 0

    for i in range(len(df) - 1):
        if i < WARMUP_PERIOD or i < skip_until:
            continue

        row = df.iloc[i]

        # 1. Trend filter: EMA50 > EMA200
        if row["ema_50"] < row["ema_200"]:
            continue

        # PHASE 1: EMA200 declining filter
        ema200_now  = row["ema_200"]
        ema200_prev = df["ema_200"].iloc[max(0, i - EMA200_LOOKBACK)]
        if ema200_now < ema200_prev:
            continue

        # 2. Regime filter: EMA50 rising + price above EMA50
        ema50_now    = row["ema_50"]
        ema50_prev   = df["ema_50"].iloc[max(0, i - REGIME_LOOKBACK)]
        ema50_slope  = (ema50_now - ema50_prev) / (ema50_prev + 1e-10)
        price_margin = (row["close"] - row["ema_50"]) / (row["ema_50"] + 1e-10)
        if ema50_slope < REGIME_MIN_SLOPE or price_margin < REGIME_MIN_MARGIN:
            continue

        # 3. Volatility floor
        if row["range_pct"] < MIN_RANGE_PCT:
            continue

        # 4. Breakout gate
        recent_high = df.iloc[i - BREAKOUT_LOOKBACK:i]["high"].max()
        if row["high"] <= recent_high:
            continue

        # 5. Entry quality filters
        if not (RSI_MIN <= row["rsi_14"] <= RSI_MAX):
            continue
        if row["vol_ratio"] < MIN_VOL_RATIO:
            continue
        if row["mom_3"] < MIN_MOM_3:
            continue

        # ML inference
        X_ml = df.iloc[[i]][FEATURE_COLS].astype(np.float64)
        if X_ml.isna().any().any():
            continue

        ml_proba = ml_model.predict_proba(X_ml)[0][1]
        if ml_proba < ML_GATE:
            continue

        ml_probs.append(ml_proba)

        signal, confidence = generate_signal(
            row["return_pct"], row["close"], row["ema_9"],
            row["rsi_14"], ml_proba, row["range_pct"]
        )

        if signal == "BUY" and confidence >= CONFIDENCE_THRESHOLD:

            # PHASE 2: POSITION SIZING
            risk_amount   = capital * RISK_PER_TRADE
            stop_distance = abs(STOP_LOSS)
            position_size = risk_amount / stop_distance
            max_position  = capital * MAX_POSITION_PCT
            position_size = min(position_size, max_position)

            entry_price = row["close"] * (1 + COSTS / 2)
            trade_ret   = None
            peak_ret    = 0.0
            exit_type   = "time"
            exit_idx    = min(i + LOOKAHEAD + 1, len(df) - 1)

            for j in range(i + 1, exit_idx):
                future   = df.iloc[j]
                high_ret = (future["high"] - entry_price) / entry_price
                low_ret  = (future["low"]  - entry_price) / entry_price

                if high_ret > peak_ret:
                    peak_ret = high_ret

                # A. Hard stop
                if low_ret <= STOP_LOSS:
                    trade_ret    = STOP_LOSS
                    exit_type    = "stop"
                    consec_stops += 1
                    cooldown     = CHOP_COOLDOWN if consec_stops >= MAX_CONSEC_STOPS else COOLDOWN_BARS
                    skip_until   = j + cooldown
                    break

                # B. Fixed profit target
                if high_ret >= PROFIT_TARGET:
                    trade_ret    = PROFIT_TARGET
                    exit_type    = "target"
                    consec_stops = 0
                    skip_until   = j + COOLDOWN_BARS
                    break

                # C. Break-even shield
                if (peak_ret >= BREAKEVEN_TRIGGER
                        and peak_ret < PROFIT_TARGET
                        and low_ret <= BREAKEVEN_LOCK):
                    trade_ret    = BREAKEVEN_LOCK
                    exit_type    = "breakeven"
                    consec_stops = 0
                    skip_until   = j + COOLDOWN_BARS
                    break

            # D. Time-based exit
            if trade_ret is None:
                exit_bar     = exit_idx - 1
                trade_ret    = (df.iloc[exit_bar]["close"] - entry_price) / entry_price
                consec_stops = 0 if trade_ret > 0 else consec_stops + 1
                skip_until   = exit_idx + COOLDOWN_BARS

            trades  += 1
            net_ret  = trade_ret - (COSTS / 2)

            pnl_dollars = position_size * net_ret
            capital    += pnl_dollars

            portfolio.apply_trade(net_ret)

            trade_log.append({
                "entry_bar":     i,
                "exit_type":     exit_type,
                "ml_proba":      round(ml_proba, 4),
                "rsi_14":        round(row["rsi_14"], 2),
                "peak_ret":      round(peak_ret, 5),
                "trade_ret":     round(trade_ret, 5),
                "net_ret":       round(net_ret, 5),
                "position_size": round(position_size, 2),
                "pnl_dollars":   round(pnl_dollars, 2),
                "capital_after": round(capital, 2),
            })

    wins      = sum(1 for t in trade_log if t["net_ret"] > 0)
    gross_p   = sum(t["net_ret"] for t in trade_log if t["net_ret"] > 0)
    gross_l   = abs(sum(t["net_ret"] for t in trade_log if t["net_ret"] < 0))
    pf        = gross_p / gross_l if gross_l > 0 else float("inf")
    wr        = wins / trades * 100 if trades > 0 else 0
    avg_ret   = sum(t["net_ret"] for t in trade_log) / trades * 100 if trades > 0 else 0
    total_pnl = capital - INITIAL_CAPITAL

    exit_breakdown = {}
    for t in trade_log:
        e = t["exit_type"]
        exit_breakdown[e] = exit_breakdown.get(e, []) + [t["net_ret"]]

    return {
        "label":          label,
        "trades":         trades,
        "win_rate":       wr,
        "avg_ret":        avg_ret,
        "pf":             pf,
        "total_pnl":      total_pnl,
        "final_capital":  capital,
        "trade_log":      trade_log,
        "exit_breakdown": exit_breakdown,
        "ml_prob_mean":   np.mean(ml_probs) if ml_probs else 0,
    }


# ============================================================
# RESULTS PRINTER
# ============================================================

def print_result(r, verbose=False):
    pf_icon  = "✅" if r["pf"] >= 1.3 else "🔶" if r["pf"] >= 0.8 else "❌"
    pnl_icon = "📈" if r["total_pnl"] >= 0 else "📉"
    print(f"\n{'─'*55}")
    print(f"📅 {r['label']}")
    print(f"{'─'*55}")
    print(f"  Trades        : {r['trades']}")
    print(f"  Win Rate      : {r['win_rate']:.1f}%")
    print(f"  Avg Return    : {r['avg_ret']:+.4f}%")
    print(f"  Profit Factor : {r['pf']:.2f}  {pf_icon}")
    print(f"  P&L ($)       : ${r['total_pnl']:+,.2f}  {pnl_icon}")
    print(f"  Final Capital : ${r['final_capital']:,.2f}")
    print(f"  ML Prob Mean  : {r['ml_prob_mean']:.4f}")
    print(f"  Exit Breakdown:")
    for etype, rets in sorted(r["exit_breakdown"].items()):
        avg = np.mean(rets) * 100
        print(f"    {etype:12s} {len(rets):2d} trades  avg {avg:+.3f}%")
    if verbose and r["trade_log"]:
        log_df = pd.DataFrame(r["trade_log"])
        print(f"\n{log_df[['entry_bar','exit_type','ml_proba','rsi_14','peak_ret','net_ret','pnl_dollars','capital_after']].to_string(index=False)}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Model not found.")

    ml_model = joblib.load(MODEL_PATH)
    print("ML PIPELINE LOADED")
    print(f"   Stop Loss     : {STOP_LOSS*100:.2f}%")
    print(f"   Profit Target : {PROFIT_TARGET*100:.2f}%")
    print(f"   Risk/Trade    : {RISK_PER_TRADE*100:.1f}% of capital")
    print(f"   ML Gate       : {ML_GATE}")
    print(f"   Confidence    : {CONFIDENCE_THRESHOLD}")

    all_results  = []
    total_capital = float(INITIAL_CAPITAL)

    if RUN_ALL_MONTHS:
        monthly_files = sorted(glob.glob(MONTHLY_GLOB))
        print(f"\nRunning {len(monthly_files)} monthly files...\n")

        for path in monthly_files:
            month = os.path.basename(path).replace("BTCUSDT-5m-", "").replace(".parquet", "")
            r = run_backtest(ml_model, path, label=month)
            if r:
                all_results.append(r)
                print_result(r, verbose=False)

        val_path = "data/processed/BTC_VALIDATION_FRESH.parquet"
        if os.path.exists(val_path):
            r = run_backtest(ml_model, val_path, label="FRESH VALIDATION")
            if r:
                all_results.append(r)
                print_result(r, verbose=False)

        if all_results:
            print(f"\n{'='*60}")
            print("FULL YEAR SUMMARY")
            print(f"{'='*60}")
            print(f"  {'Month':<22} {'Trades':>6} {'WinRate':>8} {'PF':>6} {'P&L($)':>10}")
            print(f"  {'─'*22} {'─'*6} {'─'*8} {'─'*6} {'─'*10}")

            all_nets     = []
            total_pnl    = 0
            total_trades = 0

            for r in all_results:
                icon    = "✅" if r["pf"] >= 1.3 else "🔶" if r["pf"] >= 0.8 else "❌"
                pnl_str = f"${r['total_pnl']:+,.0f}"
                print(f"  {r['label']:<22} {r['trades']:>6} {r['win_rate']:>7.1f}% {r['pf']:>5.2f} {pnl_str:>10} {icon}")
                all_nets.extend([t["net_ret"] for t in r["trade_log"]])
                total_pnl    += r["total_pnl"]
                total_trades += r["trades"]

            if all_nets:
                total_wins = sum(1 for n in all_nets if n > 0)
                gross_p    = sum(n for n in all_nets if n > 0)
                gross_l    = abs(sum(n for n in all_nets if n < 0))
                overall_pf = gross_p / gross_l if gross_l > 0 else float("inf")
                overall_wr = total_wins / len(all_nets) * 100

                print(f"\n  {'─'*56}")
                icon = "✅" if overall_pf >= 1.3 else "🔶" if overall_pf >= 0.8 else "❌"
                print(f"  {'OVERALL':<22} {total_trades:>6} {overall_wr:>7.1f}% {overall_pf:>5.2f} ${total_pnl:>+,.0f} {icon}")
                print(f"\n  Starting Capital : ${INITIAL_CAPITAL:>10,.2f}")
                print(f"  Total P&L        : ${total_pnl:>+10,.2f}")
                print(f"  Return on Capital: {total_pnl/INITIAL_CAPITAL*100:>+.2f}%")

            # Save combined trade log
            all_trades = []
            for r in all_results:
                for t in r["trade_log"]:
                    t["month"] = r["label"]
                    all_trades.append(t)
            if all_trades:
                pd.DataFrame(all_trades).to_csv(LOG_PATH, index=False)
                print(f"\nFull trade log saved -> {LOG_PATH}")

    else:
        DATA_PATH = "data/processed/BTC_VALIDATION_FRESH.parquet"
        r = run_backtest(ml_model, DATA_PATH, label=os.path.basename(DATA_PATH))
        if r:
            print_result(r, verbose=True)
            if r["trade_log"]:
                pd.DataFrame(r["trade_log"]).to_csv(LOG_PATH, index=False)
                print(f"\nTrade log saved -> {LOG_PATH}")