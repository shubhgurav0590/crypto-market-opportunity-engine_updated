"""
Paper Trader — PRODUCTION v4
- Time-based loop (never drifts, never misses candles)
- Full signal logging (every skip reason saved to CSV)
- Auto-reconnect to Binance after any error
- Telegram alerts for all key events
- Daily summary at midnight

Run: python -m live.paper_trader
"""

import time
import pandas as pd
import numpy as np
import joblib
import os
import requests
from datetime import datetime
from binance.client import Client

from strategy.signal_engine import generate_signal
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# BINANCE KEYS — loaded from .env file
# ============================================================
API_KEY    = os.getenv("API_Key")
API_SECRET = os.getenv("Secret_Key")
TESTNET    = False   # False = real Binance prices (read-only, no real trades)

# ============================================================
# TELEGRAM — loaded from .env file
# ============================================================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_PROD")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID_PROD")

# ============================================================
# STRATEGY CONFIG — must match backtest_runner.py exactly
# ============================================================
MODEL_PATH = "models/momentum_logistic.pkl"
SYMBOL     = "BTCUSDT"
INTERVAL   = "5m"
CANDLES    = 250

TRADE_LOG_FILE  = "data/processed/paper_trades.csv"
SIGNAL_LOG_FILE = "data/processed/signal_log.csv"

CONFIDENCE_THRESHOLD = 0.55
ML_GATE              = 0.49
STOP_LOSS            = -0.0025
PROFIT_TARGET        =  0.0035
RISK_PER_TRADE       =  0.01
COSTS                =  0.0006

REGIME_MIN_SLOPE  = 0.0006
REGIME_MIN_MARGIN = 0.0015
EMA200_LOOKBACK   = 50
REGIME_LOOKBACK   = 20

RSI_MIN       = 42
RSI_MAX       = 72
MIN_VOL_RATIO = 0.90
MIN_MOM_3     = 0.0002

CHECK_INTERVAL = 300   # 5 minutes

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
# STATE
# ============================================================
in_trade          = False
entry_price       = None
entry_ml          = None
entry_rsi         = None
trade_log         = []
signal_log        = []
capital           = 10_000.0
start_capital     = 10_000.0
total_trades      = 0
total_wins        = 0
last_summary_date = None


# ============================================================
# TELEGRAM FUNCTIONS
# ============================================================

def send_telegram(message):
    try:
        url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
        resp = requests.post(url, data=data, timeout=10)
        if resp.status_code != 200:
            print(f"[Telegram] Failed: {resp.text}")
    except Exception as e:
        print(f"[Telegram] Error: {e}")


def tg_startup(btc_price):
    send_telegram(
        f"PAPER TRADER v4 STARTED\n"
        f"BTC Price    : ${btc_price:,.2f}\n"
        f"Capital      : ${capital:,.2f}\n"
        f"Stop Loss    : {STOP_LOSS*100:.2f}%\n"
        f"Target       : +{PROFIT_TARGET*100:.2f}%\n"
        f"Risk/Trade   : {RISK_PER_TRADE*100:.1f}%\n"
        f"Logging all signals to signal_log.csv\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


def tg_buy(btc_price, ml_proba, rsi, stop_p, target_p, pos_size):
    send_telegram(
        f"BUY SIGNAL FIRED\n"
        f"BTC    : ${btc_price:,.2f}\n"
        f"ML     : {ml_proba:.4f}\n"
        f"RSI    : {rsi:.1f}\n"
        f"Stop   : ${stop_p:,.2f}\n"
        f"Target : ${target_p:,.2f}\n"
        f"Size   : ${pos_size:,.0f}\n"
        f"Cap    : ${capital:,.2f}\n"
        f"{datetime.now().strftime('%H:%M:%S')}"
    )


def tg_target(btc_price, ret, pnl):
    wr = total_wins / total_trades * 100 if total_trades > 0 else 0
    send_telegram(
        f"TARGET HIT - WIN\n"
        f"Exit   : ${btc_price:,.2f}\n"
        f"Return : +{ret*100:.3f}%\n"
        f"PnL    : +${pnl:.2f}\n"
        f"Cap    : ${capital:,.2f}\n"
        f"Total  : ${capital - start_capital:+,.2f}\n"
        f"Trades : {total_trades} | WR: {wr:.0f}%"
    )


def tg_stop(btc_price, ret, pnl):
    wr = total_wins / total_trades * 100 if total_trades > 0 else 0
    send_telegram(
        f"STOP LOSS HIT\n"
        f"Exit   : ${btc_price:,.2f}\n"
        f"Return : {ret*100:.3f}%\n"
        f"PnL    : -${abs(pnl):.2f}\n"
        f"Cap    : ${capital:,.2f}\n"
        f"Total  : ${capital - start_capital:+,.2f}\n"
        f"Trades : {total_trades} | WR: {wr:.0f}%"
    )


def tg_daily_summary():
    wr        = total_wins / total_trades * 100 if total_trades > 0 else 0
    pnl       = capital - start_capital
    today     = datetime.now().strftime("%Y-%m-%d")
    today_all = sum(1 for s in signal_log if s["datetime"].startswith(today))
    today_buy = sum(1 for s in signal_log if s["datetime"].startswith(today) and s["status"] == "BUY_SIGNAL")
    send_telegram(
        f"DAILY SUMMARY - {today}\n"
        f"Trades   : {total_trades}\n"
        f"Wins     : {total_wins}\n"
        f"Win Rate : {wr:.1f}%\n"
        f"P&L      : ${pnl:+,.2f}\n"
        f"Capital  : ${capital:,.2f}\n"
        f"Checks   : {today_all}\n"
        f"Near-signals : {today_buy}\n"
        f"Running normally"
    )


def tg_error(err):
    send_telegram(
        f"ERROR - AUTO RECOVERING\n"
        f"{str(err)[:200]}\n"
        f"Retrying in 15 seconds\n"
        f"{datetime.now().strftime('%H:%M:%S')}"
    )


# ============================================================
# LOGGING
# ============================================================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def save_signal(status, btc_price, reason, rsi=None, ml=None,
                conf=None, ema50_slope=None, vol_ratio=None):
    signal_log.append({
        "datetime":    datetime.now().strftime("%Y-%m-%d %H:%M"),
        "btc_price":   round(btc_price, 2),
        "status":      status,
        "reason":      reason,
        "rsi":         round(rsi, 2)        if rsi        is not None else None,
        "ml_proba":    round(ml, 4)          if ml         is not None else None,
        "confidence":  round(conf, 4)        if conf       is not None else None,
        "ema50_slope": round(ema50_slope, 6) if ema50_slope is not None else None,
        "vol_ratio":   round(vol_ratio, 3)   if vol_ratio  is not None else None,
        "capital":     round(capital, 2),
    })
    if len(signal_log) % 10 == 0:
        flush_signal_log()


def flush_signal_log():
    if signal_log:
        os.makedirs("data/processed", exist_ok=True)
        pd.DataFrame(signal_log).to_csv(SIGNAL_LOG_FILE, index=False)


def save_trade_log():
    if trade_log:
        os.makedirs("data/processed", exist_ok=True)
        pd.DataFrame(trade_log).to_csv(TRADE_LOG_FILE, index=False)


def record_trade(exit_type, entry, exit_p, ret, pnl, ml_proba, rsi):
    global total_trades, total_wins
    total_trades += 1
    if pnl > 0:
        total_wins += 1
    trade_log.append({
        "datetime":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        "exit_type": exit_type,
        "entry":     round(entry, 2),
        "exit":      round(exit_p, 2),
        "ret_pct":   round(ret * 100, 4),
        "pnl":       round(pnl, 2),
        "capital":   round(capital, 2),
        "ml_proba":  round(ml_proba, 4) if ml_proba else 0,
        "rsi_14":    round(rsi, 2),
    })
    save_trade_log()
    wr = total_wins / total_trades * 100
    log(f"   Trade #{total_trades} saved | WR={wr:.1f}% | Capital=${capital:,.2f}")


# ============================================================
# FEATURE ENGINEERING
# ============================================================

def compute_features(df):
    df = df.copy()
    df["return_pct"]  = (df["close"] - df["open"]) / df["open"]
    df["range_pct"]   = (df["high"] - df["low"]) / df["close"]
    df["vol_change"]  = df["volume"].pct_change().replace([np.inf, -np.inf], np.nan)
    df["ema_9"]   = df["close"].ewm(span=9,   adjust=False).mean()
    df["ema_50"]  = df["close"].ewm(span=50,  adjust=False).mean()
    df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()
    delta = df["close"].diff()
    gain  = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    df["rsi_14"]      = 100 - (100 / (1 + gain / loss.replace(0, 1e-10)))
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


def get_candles(client):
    raw = client.get_klines(symbol=SYMBOL, interval=INTERVAL, limit=CANDLES)
    df  = pd.DataFrame(raw, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","quote_vol","trades",
        "taker_buy_base","taker_buy_quote","ignore"
    ])
    for col in ["open","high","low","close","volume"]:
        df[col] = pd.to_numeric(df[col])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    return df.reset_index(drop=True)


# ============================================================
# SIGNAL CHECK
# ============================================================

def check_signal(client, ml_model):
    global in_trade, entry_price, entry_ml, entry_rsi, capital

    df      = get_candles(client)
    df      = compute_features(df)
    row     = df.iloc[-2]
    btc_now = float(client.get_symbol_ticker(symbol=SYMBOL)["price"])

    # EXIT LOGIC
    if in_trade and entry_price is not None:
        ret      = (btc_now - entry_price) / entry_price
        pos_size = (capital * RISK_PER_TRADE) / abs(STOP_LOSS)

        if ret <= STOP_LOSS:
            pnl      = pos_size * STOP_LOSS
            capital += pnl
            in_trade = False
            log(f"STOP | BTC={btc_now:.2f} | ret={ret*100:+.3f}% | PnL=${pnl:+.2f}")
            tg_stop(btc_now, ret, pnl)
            record_trade("stop", entry_price, btc_now, ret, pnl, entry_ml, entry_rsi or row["rsi_14"])
            save_signal("STOP", btc_now, f"Stop hit ret={ret*100:.3f}%", rsi=row["rsi_14"])
            entry_price = None
            return

        if ret >= PROFIT_TARGET:
            pnl      = pos_size * PROFIT_TARGET
            capital += pnl
            in_trade = False
            log(f"TARGET | BTC={btc_now:.2f} | ret={ret*100:+.3f}% | PnL=${pnl:+.2f}")
            tg_target(btc_now, ret, pnl)
            record_trade("target", entry_price, btc_now, ret, pnl, entry_ml, entry_rsi or row["rsi_14"])
            save_signal("TARGET", btc_now, f"Target hit ret={ret*100:.3f}%", rsi=row["rsi_14"])
            entry_price = None
            return

        log(f"IN TRADE | entry={entry_price:.2f} | now={btc_now:.2f} | ret={ret*100:+.3f}%")
        save_signal("IN_TRADE", btc_now, f"Holding ret={ret*100:.3f}%", rsi=row["rsi_14"])
        return

    # ENTRY FILTERS
    if row["ema_50"] < row["ema_200"]:
        log("Skip: EMA50 < EMA200")
        save_signal("SKIP", btc_now, "EMA50 < EMA200 (downtrend)", rsi=row["rsi_14"])
        return

    if row["ema_200"] < df["ema_200"].iloc[-(EMA200_LOOKBACK + 2)]:
        log("Skip: EMA200 declining")
        save_signal("SKIP", btc_now, "EMA200 declining (bearish month)", rsi=row["rsi_14"])
        return

    ema50_prev   = df["ema_50"].iloc[-(REGIME_LOOKBACK + 2)]
    ema50_slope  = (row["ema_50"] - ema50_prev) / (ema50_prev + 1e-10)
    price_margin = (row["close"] - row["ema_50"]) / (row["ema_50"] + 1e-10)

    if ema50_slope < REGIME_MIN_SLOPE:
        log(f"Skip: EMA50 slope={ema50_slope:.5f}")
        save_signal("SKIP", btc_now, f"EMA50 slope={ema50_slope:.5f}", rsi=row["rsi_14"], ema50_slope=ema50_slope)
        return

    if price_margin < REGIME_MIN_MARGIN:
        log(f"Skip: price margin={price_margin:.5f}")
        save_signal("SKIP", btc_now, f"price margin={price_margin:.5f}", rsi=row["rsi_14"], ema50_slope=ema50_slope)
        return

    if not (RSI_MIN <= row["rsi_14"] <= RSI_MAX):
        log(f"Skip: RSI={row['rsi_14']:.1f}")
        save_signal("SKIP", btc_now, f"RSI={row['rsi_14']:.1f} out of range", rsi=row["rsi_14"], ema50_slope=ema50_slope)
        return

    if row["vol_ratio"] < MIN_VOL_RATIO:
        log(f"Skip: vol_ratio={row['vol_ratio']:.2f}")
        save_signal("SKIP", btc_now, f"vol_ratio={row['vol_ratio']:.2f} low", rsi=row["rsi_14"], vol_ratio=row["vol_ratio"], ema50_slope=ema50_slope)
        return

    if row["mom_3"] < MIN_MOM_3:
        log(f"Skip: mom_3={row['mom_3']:.5f}")
        save_signal("SKIP", btc_now, f"mom_3={row['mom_3']:.5f} weak", rsi=row["rsi_14"], ema50_slope=ema50_slope)
        return

    X_ml = df.iloc[[-2]][FEATURE_COLS].astype(float)
    if X_ml.isna().any().any():
        log("Skip: NaN in features")
        save_signal("SKIP", btc_now, "NaN in features")
        return

    ml_proba = ml_model.predict_proba(X_ml)[0][1]
    if ml_proba < ML_GATE:
        log(f"Skip: ML={ml_proba:.4f}")
        save_signal("SKIP", btc_now, f"ML={ml_proba:.4f} below gate", rsi=row["rsi_14"], ml=ml_proba, ema50_slope=ema50_slope)
        return

    signal, confidence = generate_signal(
        row["return_pct"], row["close"], row["ema_9"],
        row["rsi_14"], ml_proba, row["range_pct"]
    )
    log(f"Signal={signal} | conf={confidence:.4f} | ML={ml_proba:.4f} | RSI={row['rsi_14']:.1f}")

    if signal != "BUY" or confidence < CONFIDENCE_THRESHOLD:
        save_signal("BUY_SIGNAL", btc_now,
                    f"Near-signal: conf={confidence:.4f} (need {CONFIDENCE_THRESHOLD})",
                    rsi=row["rsi_14"], ml=ml_proba, conf=confidence, ema50_slope=ema50_slope)
        return

    # BUY ENTRY
    entry_price  = btc_now
    entry_ml     = ml_proba
    entry_rsi    = row["rsi_14"]
    in_trade     = True

    pos_size     = (capital * RISK_PER_TRADE) / abs(STOP_LOSS)
    stop_price   = entry_price * (1 + STOP_LOSS)
    target_price = entry_price * (1 + PROFIT_TARGET)

    log(f"BUY | BTC={entry_price:.2f} | stop=${stop_price:.2f} | target=${target_price:.2f}")
    tg_buy(entry_price, ml_proba, row["rsi_14"], stop_price, target_price, pos_size)
    save_signal("BUY_ENTRY", btc_now,
                f"BUY entered conf={confidence:.4f} ML={ml_proba:.4f}",
                rsi=row["rsi_14"], ml=ml_proba, conf=confidence, ema50_slope=ema50_slope)


# ============================================================
# MAIN
# ============================================================

def main():
    global last_summary_date

    print("=" * 55)
    print("PAPER TRADER v4 - Full Signal Logging")
    print("=" * 55)
    print(f"   Symbol        : {SYMBOL}")
    print(f"   Stop Loss     : {STOP_LOSS*100:.2f}%")
    print(f"   Profit Target : +{PROFIT_TARGET*100:.2f}%")
    print(f"   Risk/Trade    : {RISK_PER_TRADE*100:.1f}% of capital")
    print(f"   Starting Cap  : ${capital:,.2f}")
    print(f"   Trade log     : {TRADE_LOG_FILE}")
    print(f"   Signal log    : {SIGNAL_LOG_FILE}")
    print("=" * 55)

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    ml_model  = joblib.load(MODEL_PATH)
    print("ML model loaded")

    client    = Client(API_KEY, API_SECRET, testnet=TESTNET)
    btc_price = float(client.get_symbol_ticker(symbol=SYMBOL)["price"])
    print(f"Binance connected | BTC = ${btc_price:,.2f}")

    tg_startup(btc_price)
    print("Telegram startup message sent")
    print(f"\nChecks every 5 min - time-based loop, never drifts\n")

    last_check        = 0
    last_summary_date = datetime.now().date()

    try:
        check_signal(client, ml_model)
        last_check = time.time()
    except Exception as e:
        log(f"Startup check error: {e}")

    while True:
        try:
            now   = time.time()
            today = datetime.now().date()

            if today != last_summary_date and datetime.now().hour == 0:
                tg_daily_summary()
                flush_signal_log()
                last_summary_date = today
                log("Daily summary sent")

            if now - last_check >= CHECK_INTERVAL:
                last_check = now
                try:
                    check_signal(client, ml_model)
                except Exception as sig_err:
                    log(f"Signal error: {sig_err}")
                    tg_error(sig_err)
                    time.sleep(15)
                    try:
                        client = Client(API_KEY, API_SECRET, testnet=TESTNET)
                        log("Reconnected to Binance")
                    except Exception as re:
                        log(f"Reconnect failed: {re}")

            time.sleep(10)

        except KeyboardInterrupt:
            pnl = capital - start_capital
            print(f"\nStopped by user.")
            print(f"   Trades   : {total_trades}")
            print(f"   Capital  : ${capital:,.2f}")
            print(f"   P&L      : ${pnl:+,.2f}")
            print(f"   Signals  : {len(signal_log)} entries logged")
            send_telegram(
                f"Paper trader stopped\n"
                f"Trades: {total_trades} | Capital: ${capital:,.2f} | P&L: ${pnl:+,.2f}"
            )
            flush_signal_log()
            save_trade_log()
            print(f"   Saved: {SIGNAL_LOG_FILE}")
            print(f"   Saved: {TRADE_LOG_FILE}")
            break

        except Exception as e:
            log(f"Main loop error: {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()