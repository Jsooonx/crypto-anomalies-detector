"""
Model Trainer — Trains an ensemble of anomaly detection models on engineered features.

Models:
  1. Isolation Forest — tree-based outlier detection (global anomalies)
  2. Local Outlier Factor (LOF) — density-based detection (local anomalies)
  3. Ensemble — flags a candle as anomalous if both models agree

All models are trained on standardized features, serialized to disk
with joblib, and evaluation metrics are saved as JSON.
"""

import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    classification_report,
    precision_score,
    recall_score,
    f1_score,
)
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler

from config.settings import (
    FEATURE_COLUMNS,
    FEATURES_DIR,
    MODEL_PARAMS,
    MODELS_DIR,
    TRAIN_TEST_SPLIT,
    RANDOM_STATE,
    PAIRS,
)


class AnomalyModelTrainer:
    """Trains, evaluates, and persists anomaly detection models."""

    def __init__(self):
        self.scaler = StandardScaler()
        self.models = {}
        self.metrics = {}

    def _prepare_data(self, df: pd.DataFrame) -> tuple:
        """
        Split data chronologically (not randomly!) and standardize features.

        Chronological split is critical for time-series data to prevent
        look-ahead bias — the model must not see future data during training.

        Returns:
            (X_train, X_test, df_test) — scaled feature arrays and the test DataFrame
        """
        feature_df = df[FEATURE_COLUMNS].copy()

        # Chronological split
        split_idx = int(len(feature_df) * TRAIN_TEST_SPLIT)
        X_train = feature_df.iloc[:split_idx].values
        X_test = feature_df.iloc[split_idx:].values
        df_test = df.iloc[split_idx:].copy()

        # Fit scaler on training data only (prevent data leakage)
        X_train = self.scaler.fit_transform(X_train)
        X_test = self.scaler.transform(X_test)

        print(f"  Train: {X_train.shape[0]:,} samples")
        print(f"  Test:  {X_test.shape[0]:,} samples")
        print(f"  Features: {X_train.shape[1]}")

        return X_train, X_test, df_test

    def _train_isolation_forest(self, X_train: np.ndarray, X_test: np.ndarray) -> np.ndarray:
        """
        Isolation Forest — isolates anomalies by random recursive partitioning.
        Anomalies require fewer splits to isolate, resulting in shorter path lengths.
        """
        print("\n  ── Isolation Forest ──")
        params = MODEL_PARAMS["isolation_forest"]

        model = IsolationForest(**params)
        model.fit(X_train)

        self.models["isolation_forest"] = model

        # Predictions: 1 = normal, -1 = anomaly
        preds = model.predict(X_test)
        scores = model.score_samples(X_test)

        n_anomalies = (preds == -1).sum()
        print(f"  Detected {n_anomalies} anomalies ({n_anomalies / len(preds) * 100:.1f}%)")
        print(f"  Score range: [{scores.min():.3f}, {scores.max():.3f}]")

        return preds

    def _train_lof(self, X_train: np.ndarray, X_test: np.ndarray) -> np.ndarray:
        """
        Local Outlier Factor — measures local density deviation of a data point
        relative to its neighbors. Points with substantially lower density
        than their neighbors are considered outliers.
        """
        print("\n  ── Local Outlier Factor ──")
        params = MODEL_PARAMS["lof"]

        model = LocalOutlierFactor(**params)
        model.fit(X_train)

        self.models["lof"] = model

        # Predictions: 1 = normal, -1 = anomaly
        preds = model.predict(X_test)
        scores = model.score_samples(X_test)

        n_anomalies = (preds == -1).sum()
        print(f"  Detected {n_anomalies} anomalies ({n_anomalies / len(preds) * 100:.1f}%)")
        print(f"  Score range: [{scores.min():.3f}, {scores.max():.3f}]")

        return preds

    def _evaluate_ensemble(
        self, if_preds: np.ndarray, lof_preds: np.ndarray, df_test: pd.DataFrame
    ) -> dict:
        """
        Ensemble evaluation — combine predictions from all models.
        A candle is flagged as anomalous only if BOTH models agree.

        Since we don't have ground-truth labels for anomalies (this is
        unsupervised learning), we evaluate using:
          - Agreement rate between models
          - Distribution of anomalies across time
          - Anomaly co-occurrence with large price moves
        """
        print("\n  ── Ensemble Evaluation ──")

        # Convert: -1 → 1 (anomaly), 1 → 0 (normal)
        if_binary = (if_preds == -1).astype(int)
        lof_binary = (lof_preds == -1).astype(int)

        # Ensemble: both models must agree
        ensemble = ((if_binary + lof_binary) >= 2).astype(int)

        # Agreement metrics
        agreement = (if_binary == lof_binary).mean()

        # Check if anomalies correlate with large price moves
        df_test = df_test.copy()
        df_test["if_anomaly"] = if_binary
        df_test["lof_anomaly"] = lof_binary
        df_test["ensemble_anomaly"] = ensemble

        # Price move analysis
        abs_returns = df_test["returns_1h"].abs()
        anomaly_mask = ensemble == 1
        normal_mask = ensemble == 0

        avg_move_anomaly = abs_returns[anomaly_mask].mean() if anomaly_mask.any() else 0
        avg_move_normal = abs_returns[normal_mask].mean() if normal_mask.any() else 0
        move_ratio = avg_move_anomaly / avg_move_normal if avg_move_normal > 0 else 0

        metrics = {
            "isolation_forest": {
                "anomalies_detected": int(if_binary.sum()),
                "anomaly_rate": float(if_binary.mean()),
            },
            "lof": {
                "anomalies_detected": int(lof_binary.sum()),
                "anomaly_rate": float(lof_binary.mean()),
            },
            "ensemble": {
                "anomalies_detected": int(ensemble.sum()),
                "anomaly_rate": float(ensemble.mean()),
                "model_agreement": float(agreement),
                "avg_price_move_anomaly": float(avg_move_anomaly),
                "avg_price_move_normal": float(avg_move_normal),
                "move_ratio": float(move_ratio),
            },
        }

        print(f"  Model agreement: {agreement:.1%}")
        print(f"  Ensemble anomalies: {ensemble.sum()}")
        print(f"  Avg |move| on anomaly candles: {avg_move_anomaly:.4f}")
        print(f"  Avg |move| on normal candles:  {avg_move_normal:.4f}")
        print(f"  Move ratio (anomaly/normal):   {move_ratio:.2f}x")

        return metrics

    def train(self, df: pd.DataFrame) -> dict:
        """
        Full training pipeline: prepare data → train models → evaluate ensemble.

        Args:
            df: Combined feature-engineered DataFrame (all pairs)

        Returns:
            Dictionary of evaluation metrics
        """
        print(f"{'=' * 50}")
        print("Model Training")
        print(f"{'=' * 50}")

        X_train, X_test, df_test = self._prepare_data(df)

        if_preds = self._train_isolation_forest(X_train, X_test)
        lof_preds = self._train_lof(X_train, X_test)

        self.metrics = self._evaluate_ensemble(if_preds, lof_preds, df_test)

        return self.metrics

    def save(self, output_dir: str = MODELS_DIR):
        """Persist trained models, scaler, and metrics to disk."""
        os.makedirs(output_dir, exist_ok=True)

        # Save models
        for name, model in self.models.items():
            path = os.path.join(output_dir, f"{name}.pkl")
            joblib.dump(model, path)
            print(f"  Saved {name} → {path}")

        # Save scaler
        scaler_path = os.path.join(output_dir, "scaler.pkl")
        joblib.dump(self.scaler, scaler_path)
        print(f"  Saved scaler → {scaler_path}")

        # Save metrics
        metrics_path = os.path.join(output_dir, "metrics.json")
        with open(metrics_path, "w") as f:
            json.dump(self.metrics, f, indent=2)
        print(f"  Saved metrics → {metrics_path}")

        print(f"\n✓ All models saved to {output_dir}")


def train_all() -> dict:
    """
    Load all feature files, combine them, and train the full model ensemble.

    Returns:
        Evaluation metrics dictionary
    """
    feature_files = [f for f in os.listdir(FEATURES_DIR) if f.endswith("_features.csv")]

    if not feature_files:
        print("✗ No feature files found. Run feature engineering first.")
        return {}

    active_pair_names = [p.replace("/", "_") for p in PAIRS]

    # Load and combine all pairs
    all_dfs = []
    for file in feature_files:
        pair_name = file.replace("_features.csv", "")
        if pair_name not in active_pair_names:
            continue
            
        df = pd.read_csv(os.path.join(FEATURES_DIR, file))
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        all_dfs.append(df)

    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.sort_values("timestamp").reset_index(drop=True)
    combined = combined.dropna(subset=FEATURE_COLUMNS)

    print(f"Training on {len(combined):,} total samples from {len(feature_files)} pairs\n")

    # Train
    trainer = AnomalyModelTrainer()
    metrics = trainer.train(combined)
    trainer.save()

    return metrics


if __name__ == "__main__":
    train_all()
