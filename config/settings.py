"""
Centralized configuration for the Crypto Anomaly Detector.
All tunable parameters live here for easy review and modification.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Exchange & Data ─────────────────────────────────────────────
EXCHANGE = "binance"
PAIRS = ["SOL/USDT", "XRP/USDT", "LINK/USDT", "BTC/USDT", "ETH/USDT", "BNB/USDT", "ADA/USDT", "DOGE/USDT"]
TIMEFRAME = "15m"
HISTORY_DAYS = 60  # 60 days of 15m candles

# ─── Feature Engineering ─────────────────────────────────────────
FEATURE_COLUMNS = [
    "returns_1h", "returns_4h", "returns_24h",
    "volatility_20", "volume_ma_ratio",
    "rsi_14", "macd_line", "macd_signal", "macd_hist",
    "ma_slope", "price_zscore",
    "bollinger_upper", "bollinger_lower", "bollinger_width",
    "atr_14", "obv_change",
]

# ─── Model Training ──────────────────────────────────────────────
TRAIN_TEST_SPLIT = 0.7
RANDOM_STATE = 42

MODEL_PARAMS = {
    "isolation_forest": {
        "n_estimators": 200,
        "contamination": 0.05,
        "max_samples": "auto",
        "random_state": RANDOM_STATE,
    },
    "lof": {
        "n_neighbors": 20,
        "contamination": 0.05,
        "novelty": True,
    },
}

# ─── Live Detection ──────────────────────────────────────────────
ENSEMBLE_THRESHOLD = 2        # How many models must agree to flag anomaly
ANOMALY_SCORE_THRESHOLD = -0.5  # Score below this = anomalous
CHECK_INTERVAL_SECONDS = 900   # 15 minutes

# ─── Paths ────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
FEATURES_DIR = os.path.join(DATA_DIR, "features")
MODELS_DIR = os.path.join(DATA_DIR, "models")
