"""
Data loading layer with CSV caching.
Fetches OHLCV data from Binance and caches results locally as CSV files
to avoid redundant API calls on subsequent runs.
"""
from __future__ import annotations

import datetime
import pathlib
from typing import Optional

import pandas as pd

from engine.binance_client import get_klines

# Resolve the data/ directory relative to this file's location
DATA_DIR: pathlib.Path = pathlib.Path(__file__).parent.parent / "data"


def _csv_path(symbol: str, interval: str) -> pathlib.Path:
    """Return the cache file path for a given symbol and interval."""
    return DATA_DIR / f"{symbol.upper()}_{interval}.csv"


def _date_to_ms(date_str: str) -> int:
    """
    Convert a 'YYYY-MM-DD' date string to a Unix timestamp in milliseconds
    at UTC midnight.
    """
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    dt = dt.replace(tzinfo=datetime.timezone.utc)
    return int(dt.timestamp() * 1000)


def fetch_and_save(
    symbol: str,
    interval: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch OHLCV data from the Binance API and save to a CSV cache file.

    Handles pagination automatically: Binance returns at most 1000 candles
    per request, so long date ranges require multiple sequential requests.

    Args:
        symbol:     Trading pair, e.g. 'BTCUSDT'.
        interval:   Candle interval, e.g. '1d', '4h'.
        start_date: Start date string 'YYYY-MM-DD' (inclusive). If None,
                    fetches from the most recent 1000 bars.
        end_date:   End date string 'YYYY-MM-DD' (inclusive). If None,
                    fetches up to the present.

    Returns:
        pd.DataFrame with OHLCV data and DatetimeIndex.
    """
    start_ms: Optional[int] = _date_to_ms(start_date) if start_date else None
    end_ms: Optional[int] = _date_to_ms(end_date) if end_date else None

    pages: list[pd.DataFrame] = []
    cursor: Optional[int] = start_ms

    print(f"Fetching {symbol} {interval} data from Binance...")

    while True:
        page = get_klines(
            symbol=symbol,
            interval=interval,
            start_time=cursor,
            end_time=end_ms,
            limit=1000,
        )

        if page.empty:
            break

        pages.append(page)
        print(f"  Fetched {len(page)} bars up to {page.index[-1].date()}")

        # If we got fewer than 1000 bars, we've reached the end
        if len(page) < 1000:
            break

        # Advance cursor past the last returned bar to avoid duplicate
        last_ts_ms = int(page.index[-1].timestamp() * 1000)
        cursor = last_ts_ms + 1

        # Safety check: stop if cursor is past end_ms
        if end_ms is not None and cursor > end_ms:
            break

    if not pages:
        print("Warning: No data fetched.")
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    all_data = pd.concat(pages)

    # Remove any duplicate index entries (can occur at page boundaries)
    all_data = all_data[~all_data.index.duplicated(keep="first")]
    all_data = all_data.sort_index()

    # Ensure data/ directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    csv_file = _csv_path(symbol, interval)
    all_data.to_csv(csv_file)
    print(f"Saved {len(all_data)} bars to {csv_file}")

    return all_data


def load_data(
    symbol: str,
    interval: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load OHLCV data, using a local CSV cache when available.

    If the cache file exists, data is read from disk (fast, no API call).
    If the cache file is missing, data is fetched from Binance and saved.

    Date filtering is applied after loading to subset the requested range.

    Args:
        symbol:     Trading pair, e.g. 'BTCUSDT'.
        interval:   Candle interval, e.g. '1d', '4h'.
        start_date: Start date string 'YYYY-MM-DD'. Optional.
        end_date:   End date string 'YYYY-MM-DD'. Optional.

    Returns:
        pd.DataFrame with OHLCV data and DatetimeIndex.
    """
    csv_file = _csv_path(symbol, interval)

    if csv_file.exists():
        print(f"Loading cached data from {csv_file}")
        df = pd.read_csv(
            csv_file,
            index_col="Datetime",
            parse_dates=True,
        )
        # Ensure index is timezone-aware UTC (CSV may strip tz info)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")

        # Apply date filtering
        if start_date:
            df = df[df.index >= pd.Timestamp(start_date, tz="UTC")]
        if end_date:
            df = df[df.index <= pd.Timestamp(end_date, tz="UTC")]

        if df.empty:
            print(
                f"Cache exists but no data in range {start_date} to {end_date}. "
                "Fetching from API..."
            )
            return fetch_and_save(symbol, interval, start_date, end_date)

        return df

    # No cache - fetch from API
    return fetch_and_save(symbol, interval, start_date, end_date)
