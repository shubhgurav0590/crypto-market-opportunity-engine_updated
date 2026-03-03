import pandas as pd
import joblib
import os
import numpy as np

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import RobustScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, roc_auc_score

from features.indicators import rsi, ema

print("✅ TRAINING MOMENTUM ML (PRODUCTION v5 — REGIME-ALIGNED)")

DATA_PATH  = "data/processed/BTCUSDT_5m_clean.parquet"
MODEL_PATH = "models/momentum_logistic.pkl"

# Must match backtest_runner.py exactly
TARGET_UP      = 0.004
TARGET_DOWN    = 0.0025
LOOKAHEAD_BARS = 24

# Regime filter — SAME values as backtest_runner.py
# Training only on bars the model will actually be deployed on
REGIME_LOOKBACK   = 20
REGIME_MIN_SLOPE  = 0.0004
REGIME_MIN_MARGIN = 0.001

# Entry quality filters — SAME as backtest_runner.py
RSI_MIN       = 42
RSI_MAX       = 72
MIN_VOL_RATIO = 0.90
MIN_MOM_3     = 0.0002


def train_model():
    if not os.path.exists(DATA_PATH):
        print(f"❌ Error: {DATA_PATH} not found.")
        return

    df = pd.read_parquet(DATA_PATH)
    if df.index.name == "open_time":
        df = df.reset_index()
    df = df.reset_index(drop=True)

    # ── FEATURE ENGINEERING ──────────────────────────────────
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

    # EMA50 slope over REGIME_LOOKBACK bars
    df["ema50_slope_reg"] = df["ema_50"].pct_change(REGIME_LOOKBACK)
    df["price_margin"]    = (df["close"] - df["ema_50"]) / (df["ema_50"] + 1e-10)

    df = df.dropna().reset_index(drop=True)
    print(f"📊 Total bars before filters: {len(df)}")

    # ── REGIME FILTER ─────────────────────────────────────────
    # Only train on bars where the model will actually be deployed.
    # Training on all conditions then deploying only in trending ones
    # causes a distribution mismatch that hurts model accuracy.
    regime_mask = (
        (df["ema_50"] > df["ema_200"]) &              # uptrend
        (df["ema50_slope_reg"] > REGIME_MIN_SLOPE) &  # EMA rising
        (df["price_margin"] > REGIME_MIN_MARGIN)       # price above EMA50
    )
    df = df[regime_mask].reset_index(drop=True)
    print(f"📊 Bars after regime filter : {len(df)}")

    # ── ENTRY QUALITY FILTER ──────────────────────────────────
    # Only train on bars that pass the same entry gates as the backtest.
    # This makes the model learn specifically from high-quality setups.
    quality_mask = (
        (df["rsi_14"] >= RSI_MIN) &
        (df["rsi_14"] <= RSI_MAX) &
        (df["vol_ratio"] >= MIN_VOL_RATIO) &
        (df["mom_3"] >= MIN_MOM_3)
    )
    df = df[quality_mask].reset_index(drop=True)
    print(f"📊 Bars after quality filter: {len(df)}")

    # ── TARGET — path-dependent label ────────────────────────
    closes = df["close"].values
    highs  = df["high"].values
    lows   = df["low"].values
    n      = len(df)

    print("⏳ Building labels...")
    labels = []
    for i in range(n):
        end    = min(i + 1 + LOOKAHEAD_BARS, n)
        entry  = closes[i]
        result = 0
        for j in range(i + 1, end):
            if (lows[j]  - entry) / entry <= -TARGET_DOWN: result = 0; break
            if (highs[j] - entry) / entry >=  TARGET_UP:   result = 1; break
        labels.append(result)

    df["target"] = labels

    pos_rate = df["target"].mean()
    print(f"📊 Class balance — 0: {(df['target']==0).sum()} | 1: {(df['target']==1).sum()}")
    print(f"📊 Positive rate: {pos_rate:.2%}")

    if pos_rate < 0.10 or pos_rate > 0.90:
        print("⚠️  Positive rate is extreme — check TARGET_UP/TARGET_DOWN values")
        return

    feature_cols = [
        "return_pct", "range_pct", "vol_change",
        "ema_dist", "ema_50_dist",
        "vol_ratio", "vol_ratio_5",
        "rsi_14", "rsi_change", "rsi_5bar_avg",
        "mom_3", "mom_6", "mom_12",
        "range_5bar", "vol_compression",
        "up_bars_10", "dist_from_high",
        "ema_9_slope", "ema_50_slope",
    ]

    X = df[feature_cols].astype(np.float64)
    y = df["target"]

    # ── TIME-SAFE SPLIT ───────────────────────────────────────
    split_idx = int(len(df) * 0.8)
    X_train, X_val = X.iloc[:split_idx].copy(), X.iloc[split_idx:].copy()
    y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

    # Clip on train bounds only — no data leakage
    clip_bounds = {}
    for col in feature_cols:
        lo, hi = X_train[col].quantile(0.01), X_train[col].quantile(0.99)
        clip_bounds[col] = (lo, hi)
        X_train[col] = X_train[col].clip(lo, hi)
        X_val[col]   = X_val[col].clip(lo, hi)

    # ── SAMPLE WEIGHTS ────────────────────────────────────────
    pos_weight     = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
    sample_weights = np.where(y_train == 1, pos_weight, 1.0)
    print(f"⚖️  Positive sample weight: {pos_weight:.2f}x")

    # ── TRAIN ─────────────────────────────────────────────────
    scaler     = RobustScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_val_sc   = scaler.transform(X_val)

    model = GradientBoostingClassifier(
        n_estimators=300,
        max_depth=3,
        learning_rate=0.03,   # slower learning = better generalisation
        subsample=0.8,
        max_features=0.7,
        min_samples_leaf=50,
        random_state=42,
    )

    print("⏳ Training (300 trees, ~3-4 mins)...")
    model.fit(X_train_sc, y_train, sample_weight=sample_weights)

    # ── EVALUATE ──────────────────────────────────────────────
    val_probs = model.predict_proba(X_val_sc)[:, 1]
    val_auc   = roc_auc_score(y_val, val_probs)

    print(f"\n📊 Train Accuracy : {model.score(X_train_sc, y_train):.2%}")
    print(f"📊 Val Accuracy   : {model.score(X_val_sc,   y_val):.2%}")
    print(f"📊 Val AUC-ROC    : {val_auc:.4f}  ← aim for > 0.58")

    # Threshold 0.40 matches CONFIDENCE_THRESHOLD logic in backtest
    print("\n📋 Validation Report (threshold=0.40):")
    print(classification_report(y_val, (val_probs >= 0.40).astype(int), digits=3))

    print("🤖 Probability Distribution:")
    for thresh in [0.40, 0.50, 0.55, 0.60]:
        count = (val_probs >= thresh).sum()
        print(f"   >{thresh:.2f} : {count:4d} signals")
    print(f"   Mean  : {val_probs.mean():.4f}")
    print(f"   Max   : {val_probs.max():.4f}")

    # Feature importances
    importance = sorted(zip(feature_cols, model.feature_importances_),
                        key=lambda x: x[1], reverse=True)
    print("\n🔍 Top 10 Feature Importances:")
    for feat, imp in importance[:10]:
        print(f"   {feat:22s} {imp:.4f}  {'█' * int(imp * 150)}")

    # ── FINAL FIT ON ALL DATA ─────────────────────────────────
    X_full = X.copy()
    for col in feature_cols:
        X_full[col] = X_full[col].clip(*clip_bounds[col])

    final_pipeline = Pipeline([
        ("scaler", RobustScaler()),
        ("model", GradientBoostingClassifier(
            n_estimators=300, max_depth=3, learning_rate=0.03,
            subsample=0.8, max_features=0.7,
            min_samples_leaf=50, random_state=42
        ))
    ])
    all_weights = np.where(y == 1, pos_weight, 1.0)
    final_pipeline.fit(X_full, y, model__sample_weight=all_weights)

    os.makedirs("models", exist_ok=True)
    joblib.dump(final_pipeline, MODEL_PATH)
    joblib.dump(clip_bounds,    MODEL_PATH.replace(".pkl", "_clip_bounds.pkl"))
    joblib.dump(feature_cols,   MODEL_PATH.replace(".pkl", "_feature_cols.pkl"))

    print(f"\n✅ Model saved       → {MODEL_PATH}")
    print(f"✅ Clip bounds saved → {MODEL_PATH.replace('.pkl', '_clip_bounds.pkl')}")
    print(f"\nNext: python -m backtest.backtest_runner")


if __name__ == "__main__":
    train_model()