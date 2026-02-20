# Backtesting Engine

A command-line backtesting engine for cryptocurrency trading strategies, powered by [backtesting.py](https://kernc.github.io/backtesting.py/) and live Binance market data.

## Features

- Fetch OHLCV data from Binance (no API key required)
- CSV caching — data is downloaded once and reused on subsequent runs
- Plug-in strategy system — drop a `.py` file in `strategies/` and run it immediately
- Full backtesting stats: return, Sharpe ratio, max drawdown, win rate, and more
- Optional interactive Bokeh chart (`--plot`)

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```bash
# Run the built-in SMA crossover strategy on BTC daily data
python engine/run_backtest.py --symbol BTCUSDT --interval 1d --cash 100000

# Specify a date range and open the interactive chart
python engine/run_backtest.py \
    --symbol ETHUSDT \
    --interval 4h \
    --start-date 2023-01-01 \
    --end-date 2024-01-01 \
    --cash 50000 \
    --plot
```

> **Note:** Use `--cash` large enough to cover the asset price. For BTC (>$16k), use at least `--cash 20000`.

## CLI Reference

| Argument | Default | Description |
|---|---|---|
| `--symbol` | *(required)* | Trading pair, e.g. `BTCUSDT`, `ETHUSDT` |
| `--interval` | `1d` | Candle interval: `1m` `5m` `15m` `1h` `4h` `1d` `1w` |
| `--strategy` | `sma_cross` | Filename stem (no `.py`) of a file in `strategies/` |
| `--cash` | `10000` | Starting capital in quote currency |
| `--commission` | `0.001` | Per-trade fee rate (`0.001` = 0.1%) |
| `--start-date` | None | Fetch/filter data from this date (`YYYY-MM-DD`) |
| `--end-date` | None | Fetch/filter data up to this date (`YYYY-MM-DD`) |
| `--plot` | False | Open interactive Bokeh chart in browser after run |

## Project Structure

```
back-testing-llm/
├── requirements.txt
├── data/                     # Cached OHLCV CSV files (auto-created)
├── strategies/
│   └── sma_cross.py          # SMA crossover sample strategy
└── engine/
    ├── binance_client.py     # Binance REST API wrapper
    ├── data_loader.py        # Fetch + CSV cache layer
    └── run_backtest.py       # CLI entry point
```

## Adding a New Strategy

1. Create a new file in `strategies/`, e.g. `strategies/rsi_strategy.py`
2. Define a class that inherits from `backtesting.Strategy`
3. Implement `init()` to declare indicators and `next()` for trading logic
4. Run it: `python engine/run_backtest.py --symbol BTCUSDT --strategy rsi_strategy`

```python
# strategies/rsi_strategy.py
import numpy as np
from backtesting import Strategy

class RsiStrategy(Strategy):
    rsi_period = 14
    overbought = 70
    oversold = 30

    def init(self):
        # declare indicators here with self.I()
        ...

    def next(self):
        # trading logic here (self.buy(), self.sell(), self.position.close())
        ...
```

## Data Caching

Downloaded data is saved as CSV files in `data/` (e.g. `data/BTCUSDT_1d.csv`).
On subsequent runs with the same symbol and interval, data is loaded from disk instantly.
To refresh the data, delete the corresponding CSV file and re-run.

## Sample Strategy: SMA Cross (`strategies/sma_cross.py`)

Buys when the fast SMA (20-period) crosses above the slow SMA (50-period),
and sells on the reverse crossover. A 2% stop-loss is placed below each entry.

Override default parameters via the `Backtest()` call or by editing the class-level variables:

```python
# strategies/sma_cross.py
class SmaCross(Strategy):
    n1 = 20              # fast SMA period
    n2 = 50              # slow SMA period
    stop_loss_pct = 0.02 # 2% stop-loss
```
