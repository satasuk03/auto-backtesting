"""
Binance public REST API client for fetching OHLCV candlestick data.
No API key required - uses public market data endpoints only.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd
import requests

BASE_URL: str = "https://api.binance.com"
KLINES_ENDPOINT: str = "/api/v3/klines"


def get_klines(
    symbol: str,
    interval: str,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    limit: int = 1000,
) -> pd.DataFrame:
    """
    Fetch candlestick (OHLCV) data from the Binance REST API.

    Args:
        symbol:     Trading pair, e.g. 'BTCUSDT'.
        interval:   Candle interval string, e.g. '1d', '4h', '1h', '15m'.
        start_time: Start of range as Unix timestamp in milliseconds (UTC).
        end_time:   End of range as Unix timestamp in milliseconds (UTC).
        limit:      Number of candles to fetch. Max 1000.

    Returns:
        pd.DataFrame with columns [Open, High, Low, Close, Volume],
        float64 dtype, and a UTC-aware DatetimeIndex named 'Datetime'.
        Returns an empty DataFrame (correct columns, no rows) if no data
        is available for the given parameters.
    """
    params: dict = {
        "symbol": symbol.upper(),
        "interval": interval,
        "limit": limit,
    }
    if start_time is not None:
        params["startTime"] = start_time
    if end_time is not None:
        params["endTime"] = end_time

    response = requests.get(
        BASE_URL + KLINES_ENDPOINT,
        params=params,
        timeout=10,
    )
    response.raise_for_status()
    raw: list = response.json()

    if not raw:
        empty = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        empty.index.name = "Datetime"
        return empty

    # Binance kline response: 12-element array per candle
    # [0] open_time_ms, [1] open, [2] high, [3] low, [4] close,
    # [5] volume, [6] close_time_ms, [7] quote_vol, [8] num_trades,
    # [9] taker_buy_base, [10] taker_buy_quote, [11] unused
    df = pd.DataFrame(raw, columns=[
        "OpenTime", "Open", "High", "Low", "Close", "Volume",
        "CloseTime", "QuoteVolume", "NumTrades",
        "TakerBuyBase", "TakerBuyQuote", "Unused",
    ])

    # Cast price/volume columns from string to float
    for col in ("Open", "High", "Low", "Close", "Volume"):
        df[col] = df[col].astype(float)

    # Build timezone-aware DatetimeIndex from open_time milliseconds
    df.index = pd.to_datetime(df["OpenTime"], unit="ms", utc=True)
    df.index.name = "Datetime"

    return df[["Open", "High", "Low", "Close", "Volume"]]
