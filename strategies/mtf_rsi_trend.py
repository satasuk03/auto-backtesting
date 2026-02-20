"""
Multi-Timeframe RSI Trend Strategy
====================================
Uses `backtesting.lib.resample_apply` to compute RSI on higher timeframes
(daily and weekly) from a lower-timeframe base chart (e.g. 4h candles).

Logic:
  - Long entry when ALL of the following hold:
      1. Weekly RSI > 50  →  long-term bullish bias
      2. Daily RSI > rsi_entry  →  medium-term momentum (not oversold)
      3. Base-TF fast SMA > slow SMA  →  short-term uptrend
      4. Price > fast SMA  →  price respecting trend

  - Exit when EITHER:
      1. Daily RSI rises above rsi_exit (overbought, take profit)
      2. Price closes below the slow SMA (trend breakdown)

  Stop-loss is fixed at `stop_loss_pct` below entry price.

Recommended usage:
  # 4-hour candles with daily + weekly RSI
  python engine/run_backtest.py --symbol BTCUSDT --interval 4h \\
      --start-date 2022-01-01 --end-date 2024-01-01 \\
      --cash 100000 --strategy mtf_rsi_trend --plot

  # Daily candles with weekly RSI as HTF filter
  python engine/run_backtest.py --symbol ETHUSDT --interval 1d \\
      --start-date 2021-01-01 --end-date 2024-01-01 \\
      --cash 100000 --strategy mtf_rsi_trend

resample_apply(rule, func, *args) docs:
  https://kernc.github.io/backtesting.py/doc/backtesting/lib.html#backtesting.lib.resample_apply
  `rule` is any pandas offset alias:
      '4h', 'D', 'W-SUN', 'ME' (monthly end), etc.
"""
from __future__ import annotations

import pandas as pd
from backtesting import Strategy
from backtesting.lib import resample_apply


# ---------------------------------------------------------------------------
# Indicator helpers — must be module-level functions for self.I() pickling
# ---------------------------------------------------------------------------

def _sma(arr: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average via pandas rolling mean."""
    return pd.Series(arr).rolling(period).mean()


def _rsi(arr: pd.Series, period: int) -> pd.Series:
    """
    Relative Strength Index (Wilder EMA approximation).
    Returns values in [0, 100]; NaN during the warm-up period.
    """
    s = pd.Series(arr)
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(span=period, min_periods=period).mean()
    avg_loss = loss.ewm(span=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

class MtfRsiTrend(Strategy):
    """
    Multi-timeframe RSI + SMA trend-following strategy.

    Parameters
    ----------
    fast_period   : Base-TF fast SMA period (default 20)
    slow_period   : Base-TF slow SMA period (default 50)
    rsi_period    : RSI lookback for both higher timeframes (default 14)
    rsi_entry     : Daily RSI must be above this to enter (default 45)
    rsi_exit      : Daily RSI above this triggers exit / overbought (default 75)
    stop_loss_pct : Fixed stop-loss below entry price (default 0.04 = 4%)
    htf_daily     : Pandas offset for the 'daily' resample (default 'D')
    htf_weekly    : Pandas offset for the 'weekly' resample (default 'W-SUN')
    """

    # --- Base timeframe trend filter ---
    fast_period: int = 20
    slow_period: int = 50

    # --- RSI settings ---
    rsi_period: int = 14
    rsi_entry: float = 45    # daily RSI must be above this to go long
    rsi_exit: float = 75     # daily RSI above this → exit (overbought)

    # --- Risk management ---
    stop_loss_pct: float = 0.04   # 4% fixed stop-loss below entry

    # --- Resample rules (pandas offset aliases) ---
    # Change to '4h'/'D' if your base data is 1h
    # Change to 'W-SUN'/'ME' if your base data is 1d
    htf_daily: str = "D"
    htf_weekly: str = "W-SUN"

    def init(self) -> None:
        close = self.data.Close

        # -- Base timeframe: SMA trend filter --
        self.sma_fast = self.I(
            _sma, close, self.fast_period,
            name=f"SMA({self.fast_period})", overlay=True,
        )
        self.sma_slow = self.I(
            _sma, close, self.slow_period,
            name=f"SMA({self.slow_period})", overlay=True,
        )

        # -- Higher timeframe RSI via resample_apply --
        # resample_apply resamples `close` to the given rule, computes
        # the function on the coarser bars, then forward-fills the result
        # back onto the original (base-TF) index.
        self.rsi_daily = resample_apply(
            self.htf_daily, _rsi, close, self.rsi_period,
            name=f"RSI_Daily({self.rsi_period})",
        )
        self.rsi_weekly = resample_apply(
            self.htf_weekly, _rsi, close, self.rsi_period,
            name=f"RSI_Weekly({self.rsi_period})",
        )

    def next(self) -> None:
        price = self.data.Close[-1]

        if not self.position:
            # --- Entry conditions (all must be true) ---
            weekly_bullish = self.rsi_weekly[-1] > 50          # HTF bias up
            daily_momentum = self.rsi_daily[-1] > self.rsi_entry  # not oversold
            base_uptrend   = self.sma_fast[-1] > self.sma_slow[-1]  # MAs aligned
            above_ma       = price > self.sma_fast[-1]          # price in trend

            if weekly_bullish and daily_momentum and base_uptrend and above_ma:
                sl = price * (1.0 - self.stop_loss_pct)
                self.buy(sl=sl)

        else:
            # --- Exit conditions (either triggers a close) ---
            overbought      = self.rsi_daily[-1] > self.rsi_exit
            trend_breakdown = price < self.sma_slow[-1]

            if overbought or trend_breakdown:
                self.position.close()
