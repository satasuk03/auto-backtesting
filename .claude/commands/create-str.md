Create a new trading strategy in the strategies/ directory.

Arguments: $ARGUMENTS
(Expected format: STRATEGY_NAME [description of the strategy logic])
Examples:
  ema_crossover EMA 9/21 crossover with RSI confirmation
  bb_mean_revert Bollinger Band mean-reversion, long only
  macd_trend MACD signal-line crossover with ATR stop-loss

Steps to follow:

1. Read docs/strategy-guide.md fully before writing any code.

2. Create strategies/STRATEGY_NAME.py (snake_case filename) with:
   - Module-level indicator helper functions (never lambdas or methods)
   - A class inheriting from backtesting.Strategy
   - Class-level parameters with type hints and sensible defaults
   - init() declaring all indicators via self.I()
   - next() with trading logic, using [-1] to access current bar
   - A position guard (if not self.position:) to prevent pyramiding
   - sl= on every self.buy() / self.sell() call

3. After creating the file, verify it by running a quick backtest:
   ```
   python engine/run_backtest.py --symbol BTCUSDT --interval 1d --cash 100000 --strategy STRATEGY_NAME
   ```
   If there are errors, fix them before finishing.

4. Report:
   - The file created
   - Key parameters and their defaults
   - The logic summary (entry/exit conditions)
   - Backtest results (Return%, Sharpe, Max Drawdown, # Trades)

Constraints:
- File must be in strategies/ and named in snake_case.py
- All indicator functions must be module-level (required by self.I())
- Use resample_apply() for any multi-timeframe indicators
- Do not hardcode symbol or data loading inside the strategy
- Follow every rule in the checklist at the bottom of docs/strategy-guide.md
