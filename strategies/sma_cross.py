"""
SMA Crossover Strategy
======================
A simple moving average crossover strategy where:
  - BUY  when the fast SMA crosses above the slow SMA
  - SELL when the slow SMA crosses above the fast SMA
  - Stop-loss is placed 2% below the entry price

Parameters (overridable via Backtest(..., SmaCross, n1=10, n2=30)):
  n1:            Fast SMA period (default: 20)
  n2:            Slow SMA period (default: 50)
  stop_loss_pct: Stop-loss percentage below entry (default: 0.02 = 2%)
"""
from __future__ import annotations

import numpy as np
from backtesting import Strategy
from backtesting.lib import crossover


def _sma(arr: np.ndarray, period: int) -> np.ndarray:
    """
    Simple Moving Average over a numpy array.
    The first (period - 1) values are set to NaN (warm-up period).
    backtesting.py automatically skips bars where any indicator is NaN.

    Must be a module-level function (not a lambda or bound method) so
    that self.I() can wrap it correctly.
    """
    result = np.full(len(arr), np.nan, dtype=float)
    for i in range(period - 1, len(arr)):
        result[i] = arr[i - period + 1 : i + 1].mean()
    return result


class SmaCross(Strategy):
    """SMA crossover strategy with configurable periods and stop-loss."""

    # Strategy parameters - can be overridden in Backtest() call
    n1: int = 20              # Fast SMA period
    n2: int = 50              # Slow SMA period
    stop_loss_pct: float = 0.02   # 2% stop-loss below entry price

    def init(self) -> None:
        """
        Declare indicators. Called once before backtesting begins.
        self.I() wraps indicator arrays so backtesting.py reveals them
        bar-by-bar during next(), simulating real-time trading.
        """
        close = self.data.Close
        self.sma_fast = self.I(
            _sma,
            close,
            self.n1,
            name=f"SMA_fast({self.n1})",
            overlay=True,
        )
        self.sma_slow = self.I(
            _sma,
            close,
            self.n2,
            name=f"SMA_slow({self.n2})",
            overlay=True,
        )

    def next(self) -> None:
        """
        Called once per bar. Make buy/sell decisions based on current
        indicator values (backtesting.py has already sliced to current bar).
        """
        # Entry signal: fast SMA crosses above slow SMA
        if crossover(self.sma_fast, self.sma_slow):
            if not self.position:
                entry_price = self.data.Close[-1]
                sl_price = entry_price * (1.0 - self.stop_loss_pct)
                self.buy(sl=sl_price)

        # Exit signal: slow SMA crosses above fast SMA (bearish crossover)
        elif crossover(self.sma_slow, self.sma_fast):
            if self.position:
                self.position.close()
