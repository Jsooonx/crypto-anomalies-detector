"""
Data Fetcher — Retrieves historical OHLCV candlestick data from crypto exchanges.

Uses the CCXT library to connect to Binance (or any supported exchange)
and downloads hourly candles for each configured trading pair.
"""

import ccxt
import pandas as pd
from datetime import datetime, timedelta
import os
import time

from config.settings import EXCHANGE, PAIRS, TIMEFRAME, HISTORY_DAYS, RAW_DIR


class CryptoDataFetcher:
    """Fetches and persists historical OHLCV data from crypto exchanges."""

    def __init__(self, exchange_id: str = EXCHANGE, pairs: list = None):
        self.exchange = getattr(ccxt, exchange_id)({
            "enableRateLimit": True,  # Respect exchange rate limits
        })
        self.pairs = pairs or PAIRS
        self.timeframe = TIMEFRAME
        self.history_days = HISTORY_DAYS

    def fetch_pair(self, pair: str) -> pd.DataFrame:
        """
        Fetch all available OHLCV candles for a single trading pair,
        paginating through the exchange API in batches of 1000.

        Args:
            pair: Trading pair symbol (e.g., "SOL/USDT")

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume, pair
        """
        since = int(
            (datetime.now() - timedelta(days=self.history_days)).timestamp() * 1000
        )
        now_ms = int(datetime.now().timestamp() * 1000)
        candles = []

        print(f"  Fetching {pair}...", end="", flush=True)

        while since < now_ms:
            try:
                batch = self.exchange.fetch_ohlcv(
                    pair, self.timeframe, since=since, limit=1000
                )
                if not batch:
                    break

                candles.extend(batch)
                since = batch[-1][0] + 1  # Move cursor past last candle

                # Progress indicator
                print(".", end="", flush=True)

                # Small delay to be respectful of rate limits
                time.sleep(self.exchange.rateLimit / 1000)

            except ccxt.NetworkError as e:
                print(f"\n  ⚠ Network error on {pair}: {e}. Retrying...")
                time.sleep(5)
            except ccxt.ExchangeError as e:
                print(f"\n  ✗ Exchange error on {pair}: {e}. Skipping.")
                break

        df = pd.DataFrame(
            candles, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["pair"] = pair

        # Remove duplicates and sort
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
        df = df.reset_index(drop=True)

        print(f" {len(df)} candles")
        return df

    def fetch_all(self) -> dict:
        """
        Fetch OHLCV data for all configured pairs and save to CSV.

        Returns:
            Dictionary mapping pair names to their DataFrames
        """
        os.makedirs(RAW_DIR, exist_ok=True)
        results = {}

        print(f"{'=' * 50}")
        print(f"Fetching {len(self.pairs)} pairs ({self.history_days} days, {self.timeframe})")
        print(f"{'=' * 50}")

        for pair in self.pairs:
            df = self.fetch_pair(pair)

            filename = os.path.join(RAW_DIR, f"{pair.replace('/', '_')}.csv")
            df.to_csv(filename, index=False)

            results[pair] = df

        total_candles = sum(len(df) for df in results.values())
        print(f"\n✓ Fetched {total_candles:,} total candles for {len(results)} pairs")
        return results


if __name__ == "__main__":
    fetcher = CryptoDataFetcher()
    fetcher.fetch_all()
