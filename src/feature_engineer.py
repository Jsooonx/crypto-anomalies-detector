"""
Feature Engineer — Computes technical indicators and statistical features
from raw OHLCV candlestick data for anomaly detection.

All computations are fully vectorized (no row-level loops) for performance.
Features are designed to capture price momentum, volatility regime changes,
and volume anomalies that often precede significant market moves.
"""

import pandas as pd
import numpy as np
import os

from config.settings import FEATURE_COLUMNS, RAW_DIR, FEATURES_DIR, PAIRS


def compute_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Percentage returns over multiple time horizons."""
    df["returns_1h"] = df["close"].pct_change(1)
    df["returns_4h"] = df["close"].pct_change(4)
    df["returns_24h"] = df["close"].pct_change(24)
    return df


def compute_volatility(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Rolling standard deviation of hourly returns (volatility proxy)."""
    df["volatility_20"] = df["returns_1h"].rolling(window=window).std()
    return df


def compute_volume_ratio(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Current volume relative to its moving average — spikes signal unusual activity."""
    vol_ma = df["volume"].rolling(window=window).mean()
    df["volume_ma_ratio"] = df["volume"] / vol_ma.replace(0, np.nan)
    return df


def compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Relative Strength Index (RSI) — momentum oscillator.
    Values above 70 suggest overbought; below 30 suggest oversold.
    Uses exponential moving average for smoothing (Wilder's method).
    """
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi_14"] = 100 - (100 / (1 + rs))
    return df


def compute_macd(
    df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    """
    Moving Average Convergence Divergence (MACD).
    Captures trend momentum via the relationship between two EMAs.
    """
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()

    df["macd_line"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd_line"].ewm(span=signal, adjust=False).mean()
    df["macd_hist"] = df["macd_line"] - df["macd_signal"]
    return df


def compute_ma_slope(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Slope of the moving average — positive = uptrend, negative = downtrend."""
    ma = df["close"].rolling(window=window).mean()
    df["ma_slope"] = ma.diff(5) / ma  # Normalized 5-period slope
    return df


def compute_price_zscore(df: pd.DataFrame, window: int = 30) -> pd.DataFrame:
    """
    Z-score of current price relative to a rolling window.
    Extreme values (|z| > 2) indicate statistically unusual price levels.
    """
    rolling_mean = df["close"].rolling(window=window).mean()
    rolling_std = df["close"].rolling(window=window).std()
    df["price_zscore"] = (df["close"] - rolling_mean) / rolling_std.replace(0, np.nan)
    return df


def compute_bollinger_bands(df: pd.DataFrame, window: int = 20, num_std: int = 2) -> pd.DataFrame:
    """
    Bollinger Bands — dynamic support/resistance based on volatility.
    Width expansion signals increasing volatility (potential anomaly).
    """
    rolling_mean = df["close"].rolling(window=window).mean()
    rolling_std = df["close"].rolling(window=window).std()

    df["bollinger_upper"] = rolling_mean + (num_std * rolling_std)
    df["bollinger_lower"] = rolling_mean - (num_std * rolling_std)
    df["bollinger_width"] = (df["bollinger_upper"] - df["bollinger_lower"]) / rolling_mean
    return df


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Average True Range (ATR) — measures market volatility
    by decomposing the full range of prices for a period.
    """
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()

    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr_14"] = true_range.rolling(window=period).mean()
    return df


def compute_obv_change(df: pd.DataFrame) -> pd.DataFrame:
    """
    On-Balance Volume (OBV) rate of change — connects volume to price direction.
    Rising OBV with falling price can signal a reversal (divergence).
    """
    direction = np.sign(df["close"].diff())
    obv = (direction * df["volume"]).cumsum()
    df["obv_change"] = obv.pct_change(10)  # 10-period rate of change
    return df


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Master function — applies all feature engineering steps in sequence.

    Args:
        df: Raw OHLCV DataFrame with columns [timestamp, open, high, low, close, volume]

    Returns:
        DataFrame with all original columns plus computed feature columns.
    """
    df = df.copy()

    # Apply all feature computations
    df = compute_returns(df)
    df = compute_volatility(df)
    df = compute_volume_ratio(df)
    df = compute_rsi(df)
    df = compute_macd(df)
    df = compute_ma_slope(df)
    df = compute_price_zscore(df)
    df = compute_bollinger_bands(df)
    df = compute_atr(df)
    df = compute_obv_change(df)

    # Replace infinities with NaN, then forward-fill
    df = df.replace([np.inf, -np.inf], np.nan)

    return df


def engineer_all_pairs() -> dict:
    """
    Apply feature engineering to all raw CSV files in data/raw/
    and save results to data/features/.

    Returns:
        Dictionary mapping pair names to their feature DataFrames
    """
    os.makedirs(FEATURES_DIR, exist_ok=True)
    results = {}

    print(f"{'=' * 50}")
    print("Feature Engineering")
    print(f"{'=' * 50}")

    raw_files = [f for f in os.listdir(RAW_DIR) if f.endswith(".csv")]

    if not raw_files:
        print("✗ No raw data files found. Run data fetching first.")
        return results

    active_pair_names = [p.replace("/", "_") for p in PAIRS]

    for file in raw_files:
        pair_name = file.replace(".csv", "")
        if pair_name not in active_pair_names:
            continue
            
        print(f"  Processing {pair_name}...", end=" ")

        df = pd.read_csv(os.path.join(RAW_DIR, file))
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Apply all features
        df_features = compute_features(df)

        # Drop rows with NaN (from rolling windows at the start)
        before = len(df_features)
        df_features = df_features.dropna(subset=FEATURE_COLUMNS)
        after = len(df_features)

        # Save
        output_path = os.path.join(FEATURES_DIR, f"{pair_name}_features.csv")
        df_features.to_csv(output_path, index=False)

        results[pair_name] = df_features
        print(f"{after} rows (dropped {before - after} from warmup)")

    total = sum(len(df) for df in results.values())
    print(f"\n✓ Engineered {total:,} rows across {len(results)} pairs")
    print(f"  Features: {len(FEATURE_COLUMNS)} columns")
    return results


if __name__ == "__main__":
    engineer_all_pairs()
