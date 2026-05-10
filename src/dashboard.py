"""
Dashboard — Flask web application for real-time anomaly monitoring.

Serves a premium dark-mode UI that displays live anomaly detection
results, model metrics, and historical performance data.
"""

import json
import os

from flask import Flask, jsonify, render_template

from config.settings import MODELS_DIR, PAIRS
from src.live_detector import LiveDetector

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"),
    static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "static"),
)

# Initialize detector (loads models once at startup)
detector = None


def get_detector():
    """Lazy-initialize the detector so Flask can start even if models aren't trained yet."""
    global detector
    if detector is None:
        try:
            detector = LiveDetector()
        except Exception as e:
            print(f"⚠ Could not initialize detector: {e}")
            return None
    return detector


@app.route("/")
def index():
    """Serve the main dashboard page."""
    return render_template("dashboard.html", pairs=PAIRS)


@app.route("/api/anomalies")
def get_anomalies():
    """
    Return latest anomaly detection results for all configured pairs.
    Called by the frontend via fetch() to update the UI.
    """
    det = get_detector()
    if det is None:
        return jsonify({"error": "Models not loaded. Run training first."}), 503

    results = det.detect_all()
    return jsonify(results)


@app.route("/api/anomalies/<pair_key>")
def get_anomaly_single(pair_key: str):
    """Return anomaly detection result for a single pair (e.g., SOL_USDT)."""
    det = get_detector()
    if det is None:
        return jsonify({"error": "Models not loaded"}), 503

    pair = pair_key.replace("_", "/")
    result = det.detect_pair(pair)
    return jsonify(result)


@app.route("/api/metrics")
def get_metrics():
    """Return saved model evaluation metrics from training."""
    metrics_path = os.path.join(MODELS_DIR, "metrics.json")
    if not os.path.exists(metrics_path):
        return jsonify({"error": "No metrics found. Run training first."}), 404

    with open(metrics_path) as f:
        metrics = json.load(f)
    return jsonify(metrics)


@app.route("/api/health")
def health():
    """Health check endpoint."""
    det = get_detector()
    return jsonify({
        "status": "healthy",
        "models_loaded": det is not None and len(det.models) > 0,
        "model_count": len(det.models) if det else 0,
        "pairs": PAIRS,
    })


if __name__ == "__main__":
    print(f"\n{'=' * 50}")
    print("Crypto Anomaly Detector — Dashboard")
    print(f"{'=' * 50}")
    print("Starting at http://localhost:5000\n")

    app.run(debug=True, port=5000, host="0.0.0.0")
