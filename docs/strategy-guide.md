# Strategy Implementation Guide for LLMs

This document is a reference for implementing trading strategies using `backtesting.py`
in this project. Read it fully before writing any strategy code.

## Rules

Read this file only as a syntax guide. But you have to create your own strategy from scratch.

---

## Project Layout

```
back-testing-llm/
├── data/                   # CSV cache (auto-created, gitignored)
├── docs/                   # This guide and other references
├── engine/
│   ├── binance_client.py   # Fetches OHLCV from Binance REST API
│   ├── data_loader.py      # CSV cache layer wrapping binance_client
│   └── run_backtest.py     # CLI entry point
├── strategies/             # Drop new strategy .py files here
│   └── sma_cross.py        # Example: SMA crossover (single TF)
└── tmp/                    # HTML chart output (auto-created, gitignored)
```

To run a strategy:

```bash
python engine/run_backtest.py \
    --symbol BTCUSDT \
    --interval 4h \
    --strategy my_strategy \      # filename stem in strategies/
    --cash 100000 \
    --start-date 2021-01-01 \
    --end-date 2024-01-01 \
    --plot
```

---

## Strategy File Rules

1. Place the file in `strategies/`, e.g. `strategies/my_strategy.py`
2. The file must define **at least one class** that subclasses `backtesting.Strategy`
3. The runner auto-discovers the first Strategy subclass — no registration needed
4. Indicator helper functions must be **module-level** (not lambdas, not methods)

---

## Strategy Skeleton

```python
from __future__ import annotations

import numpy as np
import pandas as pd
from backtesting import Strategy
from backtesting.lib import crossover, resample_apply


# ── Indicator helpers ────────────────────────────────────────────────────────
# Must be module-level functions. self.I() requires picklable callables.
# Use numpy or pandas — both work. Return an array/Series of the same length.

def _sma(arr, period):
    return pd.Series(arr).rolling(period).mean()

def _rsi(arr, period):
    s = pd.Series(arr)
    delta = s.diff()
    gain = delta.clip(lower=0).ewm(span=period, min_periods=period).mean()
    loss = (-delta).clip(lower=0).ewm(span=period, min_periods=period).mean()
    return 100 - 100 / (1 + gain / loss)


# ── Strategy class ───────────────────────────────────────────────────────────

class MyStrategy(Strategy):
    # Class-level parameters — overridable from the CLI or Backtest() call
    period: int = 20
    stop_loss_pct: float = 0.03

    def init(self) -> None:
        """Declare all indicators here. Called once before the backtest."""
        close = self.data.Close
        self.sma = self.I(_sma, close, self.period, name=f"SMA({self.period})", overlay=True)

    def next(self) -> None:
        """Called once per bar. Contains all trading logic."""
        price = self.data.Close[-1]

        if not self.position:
            if price > self.sma[-1]:
                self.buy(sl=price * (1 - self.stop_loss_pct))

        elif price < self.sma[-1]:
            self.position.close()
```

---

## `init()` — Declaring Indicators

### `self.I(func, *args, **kwargs)`

Wraps an indicator function so backtesting.py can:
- Plot it automatically
- Slice it bar-by-bar in `next()` without lookahead

```python
def init(self):
    close = self.data.Close

    # Basic usage
    self.sma = self.I(_sma, close, 20)

    # With plot labels
    self.sma = self.I(_sma, close, 20, name="SMA(20)", overlay=True)
    # overlay=True  → drawn on the price chart
    # overlay=False → drawn in a separate panel below (default)
```

**Rules for indicator functions:**
- Must accept array/Series as first argument followed by any params
- Must return an array or Series of the **same length** as input
- NaN values are fine — backtesting.py skips bars until all indicators have values
- Must be **module-level** functions, not lambdas or methods

### Available data fields in `init()` and `next()`

```python
self.data.Open    # numpy array, all bars up to current
self.data.High
self.data.Low
self.data.Close
self.data.Volume
self.data.index   # DatetimeIndex
```

Inside `next()`, `[-1]` is the current bar, `[-2]` is the previous:

```python
self.data.Close[-1]   # current close
self.data.Close[-2]   # previous close
self.sma[-1]          # current SMA value
self.sma[-2]          # previous SMA value
```

---

## `next()` — Trading Logic

### Entering a position

```python
# Market buy (executes at next bar's open)
self.buy()

# With stop-loss and take-profit
self.buy(sl=price * 0.97, tp=price * 1.09)

# With fixed size (number of units)
self.buy(size=1)

# Fractional of available cash (0 < size < 1)
self.buy(size=0.5)   # use 50% of cash
```

```python
# Market sell / short
self.sell()
self.sell(sl=price * 1.03, tp=price * 0.91)
```

**Important:** Orders execute at the **next bar's open**, not the current close.

### Closing a position

```python
self.position.close()   # close entire position at market
```

### Checking position state

```python
self.position           # falsy when flat, truthy when in a trade
self.position.size      # number of units held (negative = short)
self.position.pl        # current unrealized P&L in cash
self.position.pl_pct    # current unrealized P&L in %
```

### Modifying a live trade's stops

```python
# Access the most recent open trade
trade = self.trades[-1]
trade.sl = new_stop_price    # move stop-loss
trade.tp = new_tp_price      # move take-profit
```

---

## Utility Functions from `backtesting.lib`

### `crossover(a, b)`

Returns `True` on the single bar where `a` crosses above `b`.

```python
from backtesting.lib import crossover

if crossover(self.sma_fast, self.sma_slow):
    self.buy()

elif crossover(self.sma_slow, self.sma_fast):
    self.position.close()
```

### `resample_apply(rule, func, *args)` — Multi-Timeframe

Resamples data to a higher timeframe, applies `func`, and forward-fills the
result back onto every base bar. No lookahead bias.

```python
from backtesting.lib import resample_apply

def init(self):
    close = self.data.Close

    # Daily RSI on a 4h chart
    self.rsi_daily = resample_apply("D", _rsi, close, 14, name="RSI_D")

    # Weekly RSI on a 4h chart
    self.rsi_weekly = resample_apply("W-SUN", _rsi, close, 14, name="RSI_W")

    # 4h SMA on a 1h chart
    self.sma_4h = resample_apply("4h", _sma, close, 20, name="SMA_4h")
```

**Common pandas offset aliases:**

| Alias | Meaning |
|-------|---------|
| `"1h"` / `"4h"` | 1-hour / 4-hour bars |
| `"D"` | Calendar day |
| `"W-SUN"` | Week ending Sunday (good for 24/7 crypto) |
| `"W-FRI"` | Week ending Friday (used in original example) |
| `"ME"` | Month end |

Pick an offset **higher** than your base interval. If your base is `4h`, valid
higher TFs are `"D"`, `"W-SUN"`, `"ME"`, etc.

---

## Strategy Parameters

Declare class-level attributes with type hints. They can be overridden at runtime.

```python
class MyStrategy(Strategy):
    fast: int = 10
    slow: int = 30
    rsi_level: float = 50.0
    stop_loss_pct: float = 0.03
```

Override via Python (for optimization):

```python
bt = Backtest(data, MyStrategy, cash=100_000)
stats = bt.run(fast=20, slow=50)
```

---

## Risk Management Patterns

### Fixed stop-loss below entry

```python
price = self.data.Close[-1]
self.buy(sl=price * (1 - 0.03))   # 3% stop-loss
```

### Fixed risk-reward (1:3)

```python
price = self.data.Close[-1]
risk = price * 0.03
self.buy(sl=price - risk, tp=price + risk * 3)
```

### Trailing stop (updated each bar)

```python
def next(self):
    if self.position:
        # Trail stop to 3% below the current close
        self.trades[-1].sl = self.data.Close[-1] * 0.97
```

### No pyramiding guard

```python
if not self.position:
    self.buy(...)
```

---

## Indicator Implementations

### Implementations from scratch

All must be **module-level functions**.

```python
import numpy as np
import pandas as pd


def _sma(arr, period):
    """Simple Moving Average."""
    return pd.Series(arr).rolling(period).mean()


def _ema(arr, period):
    """Exponential Moving Average."""
    return pd.Series(arr).ewm(span=period, min_periods=period).mean()


def _rsi(arr, period):
    """Relative Strength Index (Wilder EMA)."""
    s = pd.Series(arr)
    delta = s.diff()
    gain = delta.clip(lower=0).ewm(span=period, min_periods=period).mean()
    loss = (-delta).clip(lower=0).ewm(span=period, min_periods=period).mean()
    return 100 - 100 / (1 + gain / loss)


def _atr(high, low, close, period):
    """Average True Range — pass three arrays."""
    h, l, c = pd.Series(high), pd.Series(low), pd.Series(close)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(span=period, min_periods=period).mean()


def _bbands(arr, period, std_dev=2.0):
    """Bollinger Bands — returns (upper, mid, lower) tuple."""
    s = pd.Series(arr)
    mid = s.rolling(period).mean()
    std = s.rolling(period).std()
    return mid + std * std_dev, mid, mid - std * std_dev
```

Using ATR (multiple input arrays):

```python
def init(self):
    # self.I wraps multi-input indicators — pass each array separately
    self.atr = self.I(_atr, self.data.High, self.data.Low, self.data.Close, 14,
                      name="ATR(14)", overlay=False)

def next(self):
    price = self.data.Close[-1]
    self.buy(sl=price - 2 * self.atr[-1])   # 2× ATR stop-loss
```

Using Bollinger Bands (tuple output):

```python
def init(self):
    upper, mid, lower = self.I(_bbands, self.data.Close, 20, plot=True)
    self.bb_upper = upper
    self.bb_lower = lower
```

---

### Using the `ta` Library for Indicators

The [`ta`](https://pypi.org/project/ta/) library provides ready-made technical analysis indicators built on pandas/numpy. You can use it instead of writing indicator functions from scratch.

#### Usage Pattern

Wrap `ta` calls in **module-level functions** (as required by `self.I()`):

```python
import pandas as pd
import ta

def _ta_rsi(close, period):
    return ta.momentum.RSIIndicator(pd.Series(close), window=period).rsi()

def _ta_ema(close, period):
    return ta.trend.EMAIndicator(pd.Series(close), window=period).ema_indicator()

def _ta_macd_line(close, fast, slow, signal):
    return ta.trend.MACD(pd.Series(close), window_fast=fast, window_slow=slow, window_sign=signal).macd()

def _ta_macd_signal(close, fast, slow, signal):
    return ta.trend.MACD(pd.Series(close), window_fast=fast, window_slow=slow, window_sign=signal).macd_signal()

def _ta_bb_upper(close, period, std_dev):
    return ta.volatility.BollingerBands(pd.Series(close), window=period, window_dev=std_dev).bollinger_hband()

def _ta_bb_lower(close, period, std_dev):
    return ta.volatility.BollingerBands(pd.Series(close), window=period, window_dev=std_dev).bollinger_lband()


class MyTaStrategy(Strategy):
    rsi_period: int = 14
    ema_period: int = 50

    def init(self):
        close = self.data.Close
        self.rsi = self.I(_ta_rsi, close, self.rsi_period, name="RSI", overlay=False)
        self.ema = self.I(_ta_ema, close, self.ema_period, name="EMA(50)", overlay=True)

    def next(self):
        price = self.data.Close[-1]
        if not self.position:
            if self.rsi[-1] < 30 and price > self.ema[-1]:
                self.buy(sl=price * 0.97)
        elif self.rsi[-1] > 70:
            self.position.close()
```

### Common `ta` Modules

| Module | Class | Key Method |
|--------|-------|------------|
| `ta.momentum` | `RSIIndicator(close, window)` | `.rsi()` |
| `ta.trend` | `EMAIndicator(close, window)` | `.ema_indicator()` |
| `ta.trend` | `SMAIndicator(close, window)` | `.sma_indicator()` |
| `ta.trend` | `MACD(close, window_fast, window_slow, window_sign)` | `.macd()`, `.macd_signal()`, `.macd_diff()` |
| `ta.volatility` | `BollingerBands(close, window, window_dev)` | `.bollinger_hband()`, `.bollinger_lband()`, `.bollinger_mavg()` |
| `ta.volatility` | `AverageTrueRange(high, low, close, window)` | `.average_true_range()` |
| `ta.volume` | `OnBalanceVolumeIndicator(close, volume)` | `.on_balance_volume()` |

For the full list of available indicators, visit the [ta library documentation](https://technical-analysis-library-in-python.readthedocs.io/en/latest/ta.html).

**Important:** Each `ta` indicator function wrapper must be at **module level** — do not define them inside the class or as lambdas.

---

## Full Working Examples

### Example 1 — SMA Crossover (`strategies/sma_cross.py`)

```python
from backtesting import Strategy
from backtesting.lib import crossover
import numpy as np

def _sma(arr, period):
    result = np.full(len(arr), np.nan, dtype=float)
    for i in range(period - 1, len(arr)):
        result[i] = arr[i - period + 1:i + 1].mean()
    return result

class SmaCross(Strategy):
    n1: int = 20
    n2: int = 50
    stop_loss_pct: float = 0.02

    def init(self):
        close = self.data.Close
        self.sma_fast = self.I(_sma, close, self.n1, name=f"SMA({self.n1})", overlay=True)
        self.sma_slow = self.I(_sma, close, self.n2, name=f"SMA({self.n2})", overlay=True)

    def next(self):
        if crossover(self.sma_fast, self.sma_slow):
            if not self.position:
                price = self.data.Close[-1]
                self.buy(sl=price * (1 - self.stop_loss_pct))
        elif crossover(self.sma_slow, self.sma_fast):
            if self.position:
                self.position.close()
```

### Example 2 — Multi-Timeframe RSI Trend (`strategies/mtf_rsi_trend.py`)

```python
import pandas as pd
from backtesting import Strategy
from backtesting.lib import resample_apply

def _sma(arr, period):
    return pd.Series(arr).rolling(period).mean()

def _rsi(arr, period):
    s = pd.Series(arr)
    delta = s.diff()
    gain = delta.clip(lower=0).ewm(span=period, min_periods=period).mean()
    loss = (-delta).clip(lower=0).ewm(span=period, min_periods=period).mean()
    return 100 - 100 / (1 + gain / loss)

class MtfRsiTrend(Strategy):
    fast_period: int = 20
    slow_period: int = 50
    rsi_period: int = 14
    rsi_entry: float = 45
    rsi_exit: float = 75
    stop_loss_pct: float = 0.04
    htf_daily: str = "D"
    htf_weekly: str = "W-SUN"

    def init(self):
        close = self.data.Close
        self.sma_fast  = self.I(_sma, close, self.fast_period, overlay=True)
        self.sma_slow  = self.I(_sma, close, self.slow_period, overlay=True)
        self.rsi_daily = resample_apply(self.htf_daily, _rsi, close, self.rsi_period)
        self.rsi_weekly = resample_apply(self.htf_weekly, _rsi, close, self.rsi_period)

    def next(self):
        price = self.data.Close[-1]
        if not self.position:
            if (self.rsi_weekly[-1] > 50
                    and self.rsi_daily[-1] > self.rsi_entry
                    and self.sma_fast[-1] > self.sma_slow[-1]
                    and price > self.sma_fast[-1]):
                self.buy(sl=price * (1 - self.stop_loss_pct))
        else:
            if self.rsi_daily[-1] > self.rsi_exit or price < self.sma_slow[-1]:
                self.position.close()
```

---

## Checklist Before Submitting a Strategy

- [ ] File is in `strategies/` and named in `snake_case.py`
- [ ] Class inherits from `backtesting.Strategy`
- [ ] All indicator functions are **module-level** (not inside the class or as lambdas)
- [ ] `init()` declares every indicator via `self.I()`
- [ ] `next()` uses `[-1]` to read current bar values
- [ ] Position guard (`if not self.position`) prevents multiple open trades
- [ ] Stop-loss is set on every `self.buy()` call
- [ ] `resample_apply` rule is a **higher** timeframe than the base interval
- [ ] Class-level parameters have type hints and sensible defaults
- [ ] No hardcoded symbol or data loading inside the strategy file

---

## Data Format Reference

The engine passes a `pd.DataFrame` with this structure to `Backtest()`:

| Column | Type | Notes |
|--------|------|-------|
| `Open` | float64 | |
| `High` | float64 | |
| `Low` | float64 | |
| `Close` | float64 | |
| `Volume` | float64 | |
| index | `DatetimeIndex` (UTC) | required |

Binance interval strings accepted by `--interval`:
`1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `6h`, `8h`, `12h`, `1d`, `3d`, `1w`, `1M`
