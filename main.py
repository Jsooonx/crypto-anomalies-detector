"""
Crypto Anomaly Detector — CLI Entry Point

Usage:
    python main.py --fetch       Fetch historical OHLCV data from Binance
    python main.py --engineer    Compute technical features on raw data
    python main.py --train       Train anomaly detection models
    python main.py --all         Run the full pipeline (fetch → engineer → train)
    python main.py --dashboard   Launch the Flask monitoring dashboard
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Crypto Anomaly Detector — Ensemble ML Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --all          Run the full pipeline
  python main.py --fetch        Fetch data only
  python main.py --dashboard    Start the web dashboard
        """,
    )
    parser.add_argument("--fetch", action="store_true", help="Fetch historical OHLCV data")
    parser.add_argument("--engineer", action="store_true", help="Compute technical features")
    parser.add_argument("--train", action="store_true", help="Train anomaly detection models")
    parser.add_argument("--all", action="store_true", help="Run full pipeline: fetch → engineer → train")
    parser.add_argument("--dashboard", action="store_true", help="Launch the Flask dashboard")

    args = parser.parse_args()

    # If no args provided, show help
    if not any(vars(args).values()):
        parser.print_help()
        sys.exit(0)

    # ─── Full Pipeline ─────────────────────────────────────────
    if args.all:
        args.fetch = True
        args.engineer = True
        args.train = True

    # ─── Step 1: Fetch ─────────────────────────────────────────
    if args.fetch:
        print("\n" + "=" * 60)
        print("  STEP 1: Fetching Historical Data")
        print("=" * 60 + "\n")

        from src.data_fetcher import CryptoDataFetcher

        fetcher = CryptoDataFetcher()
        fetcher.fetch_all()

    # ─── Step 2: Feature Engineering ───────────────────────────
    if args.engineer:
        print("\n" + "=" * 60)
        print("  STEP 2: Feature Engineering")
        print("=" * 60 + "\n")

        from src.feature_engineer import engineer_all_pairs

        engineer_all_pairs()

    # ─── Step 3: Model Training ────────────────────────────────
    if args.train:
        print("\n" + "=" * 60)
        print("  STEP 3: Training Models")
        print("=" * 60 + "\n")

        from src.model_trainer import train_all

        train_all()

    # ─── Dashboard ─────────────────────────────────────────────
    if args.dashboard:
        print("\n" + "=" * 60)
        print("  Launching Dashboard")
        print("=" * 60 + "\n")

        from src.dashboard import app

        app.run(debug=True, port=5000, host="0.0.0.0")

    # ─── Done ──────────────────────────────────────────────────
    if not args.dashboard:
        print("\n" + "=" * 60)
        print("  ✓ Pipeline Complete")
        print("=" * 60)
        print("\nNext steps:")
        print("  python main.py --dashboard    Launch the monitoring UI")
        print("  python src/live_detector.py   Run continuous detection\n")


if __name__ == "__main__":
    main()
