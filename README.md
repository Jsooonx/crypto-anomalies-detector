# 🔍 Crypto Anomaly Detector

**Ensemble machine learning pipeline for detecting anomalous price behavior in cryptocurrency markets.**

Built with Python, scikit-learn, and Flask — uses Isolation Forest + Local Outlier Factor (LOF) to identify statistically unusual candle patterns across multiple trading pairs.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.3+-F7931E?logo=scikitlearn&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.3+-000?logo=flask&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Architecture

```
Raw OHLCV Data → Feature Engineering → Model Training → Live Detection → Dashboard
     (CCXT)         (16 indicators)      (IF + LOF)       (Ensemble)      (Flask)
```

### Pipeline Flow

| Step | Module | Description |
|------|--------|-------------|
| 1 | `data_fetcher.py` | Fetches 6 months of hourly OHLCV data from Binance via CCXT |
| 2 | `feature_engineer.py` | Computes 16 technical indicators (RSI, MACD, Bollinger, ATR, OBV, Z-scores) |
| 3 | `model_trainer.py` | Trains Isolation Forest + LOF with chronological train/test split |
| 4 | `live_detector.py` | Loads models, scores new candles, ensemble voting |
| 5 | `dashboard.py` | Flask UI with real-time anomaly cards and model metrics |

### Models

- **Isolation Forest** — Tree-based global anomaly detection. Isolates outliers via random recursive partitioning; anomalies require fewer splits.
- **Local Outlier Factor (LOF)** — Density-based local anomaly detection. Measures density deviation relative to neighbors.
- **Ensemble** — Flags a candle as anomalous only if **both** models agree (reduces false positives).

### Features Engineered (16 total)

| Category | Features |
|----------|----------|
| **Momentum** | RSI-14, MACD (line, signal, histogram), MA slope |
| **Volatility** | 20-period rolling volatility, ATR-14, Bollinger width |
| **Price** | 1h/4h/24h returns, price Z-score, Bollinger bands |
| **Volume** | Volume/MA ratio, OBV rate of change |

---

## Quick Start

### Prerequisites

- Python 3.10+
- Internet connection (for initial data fetch from Binance)

### Installation

```bash
git clone https://github.com/yourusername/crypto-anomaly-detector.git
cd crypto-anomaly-detector

python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
```

### Run the Full Pipeline

```bash
# Fetch data → engineer features → train models (all in one)
python main.py --all
```

### Launch the Dashboard

```bash
python main.py --dashboard
# Open http://localhost:5000
```

### Run Individual Steps

```bash
python main.py --fetch       # Step 1: Fetch OHLCV data
python main.py --engineer    # Step 2: Compute features
python main.py --train       # Step 3: Train models
```

### Run Tests

```bash
pytest tests/ -v
```

---

## Project Structure

```
crypto-anomaly-detector/
├── src/
│   ├── data_fetcher.py      # CCXT → Binance OHLCV
│   ├── feature_engineer.py  # 16 technical indicators
│   ├── model_trainer.py     # Isolation Forest + LOF ensemble
│   ├── live_detector.py     # Real-time scoring engine
│   └── dashboard.py         # Flask web UI
├── config/
│   └── settings.py          # Centralized configuration
├── templates/
│   └── dashboard.html       # Dashboard UI template
├── static/
│   ├── style.css            # Premium dark-mode design
│   └── app.js               # Dashboard client logic
├── tests/
│   └── test_pipeline.py     # Synthetic data tests
├── data/                    # Generated at runtime (.gitignored)
├── main.py                  # CLI entry point
├── requirements.txt
└── README.md
```

---

## Configuration

All parameters are centralized in `config/settings.py`:

```python
PAIRS = ["SOL/USDT", "XRP/USDT", "LINK/USDT", "AERO/USDT"]
TIMEFRAME = "1h"
HISTORY_DAYS = 180

MODEL_PARAMS = {
    "isolation_forest": {"n_estimators": 200, "contamination": 0.05},
    "lof": {"n_neighbors": 20, "contamination": 0.05, "novelty": True},
}
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Chronological train/test split | Prevents look-ahead bias in time-series evaluation |
| Unsupervised models only | No ground-truth anomaly labels available for crypto |
| Ensemble voting (2/2 agreement) | Reduces false positives by requiring consensus |
| Move ratio evaluation | Validates that flagged anomalies correlate with larger price movements |
| Vectorized feature engineering | No row-level loops; pure pandas/numpy for performance |

---

## License

MIT

---

*Built as a portfolio project demonstrating ML engineering, data pipeline design, and real-time monitoring.*
