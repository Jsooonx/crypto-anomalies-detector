"""
Live Detector — Loads trained models and scores incoming candle data in real-time.

This module bridges the gap between the offline training pipeline and
the static Vercel dashboard, providing a simple API for scoring new data.
"""

import json
import os
import time
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

from config.settings import (
    ANOMALY_SCORE_THRESHOLD,
    CHECK_INTERVAL_SECONDS,
    ENSEMBLE_THRESHOLD,
    FEATURE_COLUMNS,
    MODELS_DIR,
)
from src.data_fetcher import CryptoDataFetcher
from src.feature_engineer import compute_features


class LiveDetector:
    """Loads trained models and performs real-time anomaly scoring."""

    def __init__(self, model_dir: str = MODELS_DIR):
        self.model_dir = model_dir
        # Restrict fetching to only the last 10 days for live detection to prevent OOM Killed errors
        self.models = {}
        self.scaler = None
        # Note: We intentionally do NOT load models here anymore.
        # They will be loaded lazily to save RAM when CCXT is active.

    def _load_models(self):
        """Load all trained models and the scaler from disk."""
        model_files = {
            "isolation_forest": "isolation_forest.pkl",
            "lof": "lof.pkl",
        }

        for name, filename in model_files.items():
            path = os.path.join(self.model_dir, filename)
            if os.path.exists(path):
                self.models[name] = joblib.load(path)
                print(f"  ✓ Loaded {name}")
            else:
                print(f"  ⚠ Model not found: {path}")

        scaler_path = os.path.join(self.model_dir, "scaler.pkl")
        if os.path.exists(scaler_path):
            self.scaler = joblib.load(scaler_path)
            print(f"  ✓ Loaded scaler")
        else:
            print(f"  ⚠ Scaler not found: {scaler_path}")

        print(f"  Loaded {len(self.models)} models")

    def detect_pair(self, pair: str, df: pd.DataFrame) -> dict:
        """
        Engineer features and score the most recent candle with all loaded models.

        Args:
            pair: Trading pair symbol (e.g., "SOL/USDT")
            df: DataFrame containing the fetched OHLCV data

        Returns:
            Dictionary with pair, price, individual model scores, and ensemble flag
        """
        try:
            # Engineer features
            df_features = compute_features(df)
            df_features = df_features.dropna(subset=FEATURE_COLUMNS)

            if df_features.empty:
                return self._error_result(pair, "Insufficient data after feature engineering")

            # Get the latest row's features
            latest = df_features.iloc[-1]
            feature_values = latest[FEATURE_COLUMNS].values.reshape(1, -1)

            # Standardize using the training scaler
            if self.scaler is not None:
                feature_values = self.scaler.transform(feature_values)

            # Score with each model
            scores = {}
            anomaly_votes = 0

            for name, model in self.models.items():
                score = model.score_samples(feature_values)[0]
                prediction = model.predict(feature_values)[0]

                scores[name] = {
                    "score": float(score),
                    "is_anomaly": bool(prediction == -1),
                }

                if prediction == -1:
                    anomaly_votes += 1

            # Ensemble decision
            ensemble_flag = anomaly_votes >= ENSEMBLE_THRESHOLD

            return {
                "pair": pair,
                "timestamp": str(latest["timestamp"]),
                "close": float(latest["close"]),
                "volume": float(latest["volume"]),
                "history": df_features["close"].tail(20).tolist(),
                "chart_data": [
                    {
                        "time": int(row.timestamp.timestamp()),
                        "open": float(row.open),
                        "high": float(row.high),
                        "low": float(row.low),
                        "close": float(row.close)
                    }
                    for row in df.tail(100).itertuples()
                ],
                "scores": scores,
                "anomaly_votes": anomaly_votes,
                "anomaly_flag": ensemble_flag,
                "status": "ok",
            }

        except Exception as e:
            return self._error_result(pair, str(e))

    def detect_all(self) -> dict:
        """
        Run anomaly detection on all configured pairs.
        Uses a two-step approach to save RAM: Fetch all data first, free CCXT, then load models.
        """
        import gc
        results = {}
        raw_data = {}

        # STEP 1: Fetch data (CCXT takes ~50MB RAM)
        fetcher = CryptoDataFetcher()
        fetcher.history_days = 10  # Only need recent history for live mode
        
        for pair in fetcher.pairs:
            try:
                df = fetcher.fetch_pair(pair)
                raw_data[pair] = df.tail(100).reset_index(drop=True)
            except Exception as e:
                results[pair] = self._error_result(pair, str(e))
                
        # Free CCXT from memory completely before loading scikit-learn
        del fetcher
        gc.collect()

        # STEP 2: Load Models (scikit-learn takes ~40MB RAM)
        if not self.models:
            self._load_models()

        # STEP 3: Process features and predict
        for pair, df in raw_data.items():
            results[pair] = self.detect_pair(pair, df)
            
        return results

    def run_continuous(self):
        """
        Run the detector in a continuous loop, checking all pairs
        at the configured interval. Prints results to stdout.
        """
        print(f"\n{'=' * 50}")
        print(f"Live Anomaly Detector")
        print(f"{'=' * 50}\n")

        while True:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{timestamp}] Scanning...")

            results = self.detect_all()
            
            # Add metadata for the frontend
            output_data = {
                "last_updated": timestamp,
                "anomalies": results
            }

            # Export to public JSON
            public_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
            os.makedirs(public_dir, exist_ok=True)
            
            with open(os.path.join(public_dir, "anomalies.json"), "w") as f:
                json.dump(output_data, f)
                
            # Copy metrics to public
            metrics_src = os.path.join(self.model_dir, "metrics.json")
            if os.path.exists(metrics_src):
                import shutil
                shutil.copy(metrics_src, os.path.join(public_dir, "metrics.json"))
                
            print(f"  ✓ Exported results to public/")

            for pair, result in results.items():
                if result["status"] != "ok":
                    print(f"  {pair}: ERROR — {result.get('error', 'unknown')}")
                    continue

                flag = "🚨 ANOMALY" if result["anomaly_flag"] else "✓ Normal"
                print(
                    f"  {pair}: ${result['close']:.4f} | "
                    f"{flag} | "
                    f"Votes: {result['anomaly_votes']}/{len(self.models)}"
                )

            if os.environ.get("RUN_ONCE") == "true":
                print("\nRun once complete. Exiting.")
                break

            time.sleep(CHECK_INTERVAL_SECONDS)

    @staticmethod
    def _error_result(pair: str, error: str) -> dict:
        """Return a standardized error result dict."""
        return {
            "pair": pair,
            "timestamp": str(datetime.now()),
            "close": 0,
            "volume": 0,
            "scores": {},
            "anomaly_votes": 0,
            "anomaly_flag": False,
            "status": "error",
            "error": error,
        }


if __name__ == "__main__":
    detector = LiveDetector()
    detector.run_continuous()
