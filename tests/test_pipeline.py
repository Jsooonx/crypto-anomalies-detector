"""
Tests for the Crypto Anomaly Detection Pipeline.

Tests use synthetic data to verify the feature engineering and model
training pipelines work correctly without requiring network access.
"""

import json
import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from src.feature_engineer import compute_features
from src.model_trainer import AnomalyModelTrainer
from config.settings import FEATURE_COLUMNS


# ─── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def sample_ohlcv():
    """Generate synthetic OHLCV data for testing."""
    np.random.seed(42)
    n = 500  # Enough for rolling windows to warm up

    # Simulate a random walk with realistic price dynamics
    returns = np.random.normal(0.0002, 0.015, n)
    close = 100 * np.cumprod(1 + returns)

    df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=n, freq="h"),
        "open": close * (1 + np.random.normal(0, 0.002, n)),
        "high": close * (1 + np.abs(np.random.normal(0, 0.01, n))),
        "low": close * (1 - np.abs(np.random.normal(0, 0.01, n))),
        "close": close,
        "volume": np.random.lognormal(10, 1, n),
        "pair": "TEST/USDT",
    })

    return df


@pytest.fixture
def feature_df(sample_ohlcv):
    """Pre-computed features from sample data."""
    df = compute_features(sample_ohlcv)
    df = df.dropna(subset=FEATURE_COLUMNS)
    return df


# ─── Feature Engineering Tests ────────────────────────────────

class TestFeatureEngineering:
    """Tests for the feature engineering pipeline."""

    def test_compute_features_returns_all_columns(self, sample_ohlcv):
        """All expected feature columns should be present after computation."""
        result = compute_features(sample_ohlcv)

        for col in FEATURE_COLUMNS:
            assert col in result.columns, f"Missing feature column: {col}"

    def test_compute_features_no_infinities(self, sample_ohlcv):
        """No infinite values should remain after feature computation."""
        result = compute_features(sample_ohlcv)

        for col in FEATURE_COLUMNS:
            inf_count = np.isinf(result[col]).sum()
            assert inf_count == 0, f"Column {col} has {inf_count} infinite values"

    def test_rsi_bounded(self, sample_ohlcv):
        """RSI should be bounded between 0 and 100."""
        result = compute_features(sample_ohlcv)
        rsi = result["rsi_14"].dropna()

        assert rsi.min() >= 0, f"RSI below 0: {rsi.min()}"
        assert rsi.max() <= 100, f"RSI above 100: {rsi.max()}"

    def test_returns_are_reasonable(self, sample_ohlcv):
        """Percentage returns should be within reasonable bounds."""
        result = compute_features(sample_ohlcv)

        for col in ["returns_1h", "returns_4h", "returns_24h"]:
            values = result[col].dropna()
            # Returns shouldn't exceed ±50% for normal data
            assert values.abs().max() < 0.5, f"{col} has extreme value: {values.abs().max()}"

    def test_feature_count_after_dropna(self, feature_df):
        """After dropping NaN warmup rows, we should still have substantial data."""
        assert len(feature_df) > 400, f"Too few rows after dropna: {len(feature_df)}"

    def test_original_columns_preserved(self, sample_ohlcv):
        """Original OHLCV columns should still be present."""
        result = compute_features(sample_ohlcv)

        for col in ["timestamp", "open", "high", "low", "close", "volume"]:
            assert col in result.columns, f"Missing original column: {col}"


# ─── Model Training Tests ─────────────────────────────────────

class TestModelTrainer:
    """Tests for the model training pipeline."""

    def test_trainer_produces_models(self, feature_df):
        """Training should produce both Isolation Forest and LOF models."""
        trainer = AnomalyModelTrainer()
        metrics = trainer.train(feature_df)

        assert "isolation_forest" in trainer.models
        assert "lof" in trainer.models

    def test_trainer_produces_scaler(self, feature_df):
        """A fitted scaler should be available after training."""
        trainer = AnomalyModelTrainer()
        trainer.train(feature_df)

        assert trainer.scaler is not None
        assert hasattr(trainer.scaler, "mean_"), "Scaler was not fitted"

    def test_metrics_structure(self, feature_df):
        """Metrics should contain expected keys for all models."""
        trainer = AnomalyModelTrainer()
        metrics = trainer.train(feature_df)

        assert "isolation_forest" in metrics
        assert "lof" in metrics
        assert "ensemble" in metrics
        assert "model_agreement" in metrics["ensemble"]
        assert "move_ratio" in metrics["ensemble"]

    def test_anomaly_rate_within_bounds(self, feature_df):
        """Anomaly rate should be reasonable (not 0% and not 100%)."""
        trainer = AnomalyModelTrainer()
        metrics = trainer.train(feature_df)

        for model in ["isolation_forest", "lof"]:
            rate = metrics[model]["anomaly_rate"]
            assert 0.0 < rate < 0.7, f"{model} anomaly rate is extreme: {rate}"

    def test_save_and_load(self, feature_df):
        """Models should be serializable and loadable."""
        trainer = AnomalyModelTrainer()
        trainer.train(feature_df)

        with tempfile.TemporaryDirectory() as tmpdir:
            trainer.save(output_dir=tmpdir)

            # Check files exist
            assert os.path.exists(os.path.join(tmpdir, "isolation_forest.pkl"))
            assert os.path.exists(os.path.join(tmpdir, "lof.pkl"))
            assert os.path.exists(os.path.join(tmpdir, "scaler.pkl"))
            assert os.path.exists(os.path.join(tmpdir, "metrics.json"))

            # Check metrics JSON is valid
            with open(os.path.join(tmpdir, "metrics.json")) as f:
                loaded_metrics = json.load(f)
            assert "ensemble" in loaded_metrics

    def test_model_agreement_positive(self, feature_df):
        """Model agreement should be positive (models should agree on most points)."""
        trainer = AnomalyModelTrainer()
        metrics = trainer.train(feature_df)

        agreement = metrics["ensemble"]["model_agreement"]
        assert agreement > 0.5, f"Model agreement too low: {agreement}"


# ─── Integration Test ─────────────────────────────────────────

class TestPipelineIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline_synthetic(self, sample_ohlcv):
        """The full pipeline should work end-to-end on synthetic data."""
        # Step 1: Feature engineering
        df_features = compute_features(sample_ohlcv)
        df_features = df_features.dropna(subset=FEATURE_COLUMNS)
        assert len(df_features) > 0

        # Step 2: Model training
        trainer = AnomalyModelTrainer()
        metrics = trainer.train(df_features)
        assert "ensemble" in metrics

        # Step 3: Scoring new data (simulate live detection)
        latest = df_features[FEATURE_COLUMNS].iloc[-1:].values
        scaled = trainer.scaler.transform(latest)

        for name, model in trainer.models.items():
            score = model.score_samples(scaled)
            assert len(score) == 1
            assert np.isfinite(score[0]), f"{name} produced non-finite score"
