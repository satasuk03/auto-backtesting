# Let an LLM be your quant.

Backtesting engine for AI-generated crypto trading strategies on Binance data.

Describe a strategy in plain English, let an LLM write the code, and get full backtest results in seconds — no data wrangling, no boilerplate, just results.

## TL;DR

1. Install dependencies
```bash
pip install -r requirements.txt
```
2. Open your Claude Code
3. Ask Claude to fetch data (e.g. `fetch data for BTCUSDT 5m, 30m, 1h, 4h, 1d. most recent data in these 3 months`)
4. Ask Claude to create a strategy and test it (might tell Claude to keep iterating until you get the desired results)

## How it works

1. **Describe** a strategy to your LLM ("Buy when MACD crosses up, sell on crossdown")
2. **Drop** the generated `.py` file into `strategies/`
3. **Run** the backtest and iterate

The engine handles everything else: fetching Binance data, caching, running the simulation, and producing an interactive chart.

## Quick Start

```bash
pip install -r requirements.txt

# Run a strategy on BTC daily data
python engine/run_backtest.py --symbol BTCUSDT --interval 1d --cash 100000 --strategy macd_cross

# With date range and interactive chart
python engine/run_backtest.py \
    --symbol BTCUSDT \
    --interval 4h \
    --start-date 2021-01-01 \
    --end-date 2024-01-01 \
    --cash 100000 \
    --strategy macd_cross \
    --plot
```

> **Note:** Use `--cash` large enough to cover the asset price. For BTC (>$16k), use at least `--cash 20000`.

## Prompting an LLM

Point your LLM at `docs/strategy-guide.md` before asking it to write a strategy. It covers all the conventions the engine expects — indicator declarations, crossover helpers, stop-loss patterns, and multi-timeframe setups.

Example prompt:
> "Read docs/strategy-guide.md, then write a strategy that buys when RSI crosses above 50 and sells when it crosses below. Use a 3% stop-loss."

The LLM will produce a ready-to-run file. Drop it in `strategies/` and backtest immediately.

## Included Strategies

| File | Description |
|---|---|
| `sma_cross.py` | Fast/slow SMA crossover with stop-loss |
| `mtf_rsi_trend.py` | Multi-timeframe RSI + SMA trend filter |
| `macd_cross.py` | MACD / signal line crossover |

## CLI Reference

| Argument | Default | Description |
|---|---|---|
| `--symbol` | *(required)* | Trading pair, e.g. `BTCUSDT`, `ETHUSDT` |
| `--interval` | `1d` | Candle interval: `1m` `5m` `15m` `1h` `4h` `1d` `1w` |
| `--strategy` | `sma_cross` | Filename stem (no `.py`) of a file in `strategies/` |
| `--cash` | `10000` | Starting capital in quote currency |
| `--commission` | `0.001` | Per-trade fee rate (`0.001` = 0.1%) |
| `--start-date` | None | Filter data from this date (`YYYY-MM-DD`) |
| `--end-date` | None | Filter data up to this date (`YYYY-MM-DD`) |
| `--plot` | False | Open interactive Bokeh chart in browser after run |

## Project Structure

```
back-testing-llm/
├── docs/
│   └── strategy-guide.md     # Feed this to your LLM before prompting
├── strategies/               # Drop generated strategy files here
│   ├── sma_cross.py
│   ├── mtf_rsi_trend.py
│   └── macd_cross.py
├── engine/
│   ├── binance_client.py     # Binance REST API wrapper (no auth required)
│   ├── data_loader.py        # Fetch + CSV cache layer
│   └── run_backtest.py       # CLI entry point
└── data/                     # Cached OHLCV CSV files (auto-created)
```

## Data Caching

Data is fetched from Binance once and saved to `data/` (e.g. `data/BTCUSDT_1d.csv`). Subsequent runs load from disk instantly. To force a fresh fetch, delete the CSV:

```bash
rm data/BTCUSDT_1d.csv
```
