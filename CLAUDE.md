# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running Backtests

```bash
# Basic run
python engine/run_backtest.py --symbol BTCUSDT --interval 1d --cash 100000

# With date range and interactive plot
python engine/run_backtest.py --symbol BTCUSDT --interval 4h \
    --start-date 2021-01-01 --end-date 2024-01-01 \
    --cash 100000 --strategy mtf_rsi_trend --plot

# Use a different strategy (filename stem, no .py)
python engine/run_backtest.py --symbol ETHUSDT --strategy my_strategy
```

Always run from the **project root**, not from inside `engine/`. The script adds the project root to `sys.path` automatically.

Use `--cash` large enough to cover the asset price (BTC > $16k needs at least `--cash 20000`).

## Installing Dependencies

```bash
pip install -r requirements.txt
```

## Architecture

**Data flow:**
```
Binance REST API
    └─► engine/binance_client.py   get_klines() → pd.DataFrame (OHLCV, UTC DatetimeIndex)
            └─► engine/data_loader.py   load_data() → CSV cache layer + pagination
                    └─► engine/run_backtest.py   CLI → Backtest(data, StrategyClass)
                                                          └─► strategies/*.py
```

**Key design decisions:**
- `binance_client.py` is stateless — one public function, no auth, no file I/O
- `data_loader.py` handles pagination (Binance max 1000 bars/request) and caches to `data/SYMBOL_interval.csv`; on subsequent runs with the same symbol/interval it reads from disk without hitting the API
- `run_backtest.py` discovers strategy classes dynamically via `importlib` — any `.py` file dropped in `strategies/` that subclasses `backtesting.Strategy` is immediately usable via `--strategy filename`
- Every run saves an HTML chart to `tmp/SYMBOL_interval_StrategyName.html`; `--plot` additionally opens it in the browser

## Adding a Strategy

Create `strategies/my_strategy.py`. The file must contain a class that inherits from `backtesting.Strategy`. The runner picks it up automatically — no registration required.

Read `docs/strategy-guide.md` before writing any strategy code. It covers:
- `self.I()` for declaring indicators (must be module-level functions, not lambdas)
- `self.buy()` / `self.sell()` / `self.position.close()` with `sl=` and `tp=`
- `resample_apply(rule, func, ...)` for multi-timeframe indicators
- Common indicator implementations (SMA, EMA, RSI, ATR, Bollinger Bands)
- A pre-submit checklist

## Data Format

`backtesting.py` requires a `pd.DataFrame` with float64 columns `Open, High, Low, Close, Volume` and a UTC-aware `DatetimeIndex`. The engine produces this automatically from Binance data.

Valid `--interval` values: `1m 3m 5m 15m 30m 1h 2h 4h 6h 8h 12h 1d 3d 1w 1M`

## Cache Management

Delete a CSV in `data/` to force a fresh fetch:
```bash
rm data/BTCUSDT_4h.csv
```
