"""
Backtesting CLI Runner
======================
Orchestrates data loading, strategy importing, backtest execution,
and result display.

Usage:
    python engine/run_backtest.py --symbol BTCUSDT --interval 1d
    python engine/run_backtest.py --symbol ETHUSDT --interval 4h \\
        --start-date 2023-01-01 --end-date 2024-01-01 --plot
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys
import types
from typing import Type

# Ensure the project root is on sys.path when the script is run directly
# (e.g., `python engine/run_backtest.py`). Must happen before any engine imports.
_PROJECT_ROOT = pathlib.Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd
from backtesting import Backtest, Strategy

from engine.data_loader import load_data

# Root of the project (parent of engine/)
PROJECT_ROOT: pathlib.Path = pathlib.Path(__file__).parent.parent
STRATEGIES_DIR: pathlib.Path = PROJECT_ROOT / "strategies"


def _load_strategy_class(strategy_name: str) -> Type[Strategy]:
    """
    Dynamically import a Strategy subclass from strategies/<strategy_name>.py.

    The module must define at least one class that subclasses
    backtesting.Strategy. If multiple strategy classes are found, the first
    one (in definition order) is returned.

    Args:
        strategy_name: Filename stem without '.py', e.g. 'sma_cross'.

    Returns:
        The Strategy subclass (not an instance).

    Raises:
        FileNotFoundError: If the strategy file does not exist.
        ValueError:        If no Strategy subclass is found in the file.
    """
    module_path = STRATEGIES_DIR / f"{strategy_name}.py"

    if not module_path.exists():
        available = [p.stem for p in STRATEGIES_DIR.glob("*.py")]
        raise FileNotFoundError(
            f"Strategy file not found: {module_path}\n"
            f"Available strategies: {available}"
        )

    spec = importlib.util.spec_from_file_location(strategy_name, module_path)
    module: types.ModuleType = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    candidates: list[Type[Strategy]] = [
        obj
        for name, obj in vars(module).items()
        if isinstance(obj, type)
        and issubclass(obj, Strategy)
        and obj is not Strategy
    ]

    if not candidates:
        raise ValueError(
            f"No Strategy subclass found in {module_path}. "
            "Make sure your strategy class inherits from backtesting.Strategy."
        )

    return candidates[0]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a backtest against Binance OHLCV data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--symbol",
        type=str,
        required=True,
        help="Trading pair symbol, e.g. BTCUSDT",
    )
    parser.add_argument(
        "--interval",
        type=str,
        default="1d",
        help="Candle interval: 1m, 5m, 15m, 1h, 4h, 1d, 1w, etc.",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="sma_cross",
        help="Strategy filename stem (without .py) inside strategies/",
    )
    parser.add_argument(
        "--cash",
        type=float,
        default=10_000.0,
        help="Starting capital in quote currency",
    )
    parser.add_argument(
        "--commission",
        type=float,
        default=0.001,
        help="Per-trade commission rate (0.001 = 0.1%%)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        dest="start_date",
        help="Filter data start date, format YYYY-MM-DD",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        dest="end_date",
        help="Filter data end date, format YYYY-MM-DD",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        default=False,
        help="Open an interactive Bokeh chart after the backtest",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    symbol = args.symbol.upper()

    # ------------------------------------------------------------------ #
    # 1. Load OHLCV data (from cache or Binance API)
    # ------------------------------------------------------------------ #
    print(f"\nLoading data: {symbol} | {args.interval}")
    data: pd.DataFrame = load_data(
        symbol=symbol,
        interval=args.interval,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    if data.empty:
        print(
            "Error: No data available for the given parameters.\n"
            f"  Symbol:   {symbol}\n"
            f"  Interval: {args.interval}\n"
            f"  From:     {args.start_date or 'not specified'}\n"
            f"  To:       {args.end_date or 'not specified'}"
        )
        sys.exit(1)

    print(
        f"Loaded {len(data)} bars | "
        f"{data.index[0].date()} to {data.index[-1].date()}"
    )

    # ------------------------------------------------------------------ #
    # 2. Load strategy class dynamically
    # ------------------------------------------------------------------ #
    print(f"\nLoading strategy: {args.strategy}")
    try:
        StrategyClass = _load_strategy_class(args.strategy)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    print(f"Strategy class: {StrategyClass.__name__}")

    # ------------------------------------------------------------------ #
    # 3. Run backtest
    # ------------------------------------------------------------------ #
    print("\nRunning backtest...")
    bt = Backtest(
        data=data,
        strategy=StrategyClass,
        cash=args.cash,
        commission=args.commission,
    )
    stats = bt.run()

    # ------------------------------------------------------------------ #
    # 4. Display results
    # ------------------------------------------------------------------ #
    separator = "=" * 60
    print(f"\n{separator}")
    print(f"  Results: {symbol} | {args.interval} | {StrategyClass.__name__}")
    print(separator)
    print(stats.to_string())
    print(separator)

    # ------------------------------------------------------------------ #
    # 5. Save HTML output to tmp/ and optionally open in browser
    # ------------------------------------------------------------------ #
    html_filename = (
        PROJECT_ROOT / "tmp"
        / f"{symbol}_{args.interval}_{StrategyClass.__name__}.html"
    )
    bt.plot(filename=str(html_filename), open_browser=args.plot)
    print(f"\nChart saved to {html_filename}")


if __name__ == "__main__":
    main()
