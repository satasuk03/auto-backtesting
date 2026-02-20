Fetch and cache OHLCV data from Binance for a trading pair.

Arguments: $ARGUMENTS
(Expected format: SYMBOL INTERVAL [START_DATE] [END_DATE])
Examples:
  BTCUSDT 1d
  ETHUSDT 4h 2022-01-01 2024-01-01

Parse the arguments above and run the following Python one-liner from the project root to fetch and cache the data:

```
python -c "
import sys; sys.path.insert(0, '.')
from engine.data_loader import load_data
df = load_data(symbol='SYMBOL', interval='INTERVAL', start_date=START_OR_NONE, end_date=END_OR_NONE)
print(f'Fetched {len(df)} bars from {df.index[0].date()} to {df.index[-1].date()}')
print(df.tail())
"
```

Rules:
- SYMBOL must be uppercase (e.g. BTCUSDT, ETHUSDT, SOLUSDT)
- INTERVAL must be a valid Binance interval: 1m 3m 5m 15m 30m 1h 2h 4h 6h 8h 12h 1d 3d 1w 1M
- START_DATE and END_DATE are optional; use None if not provided
- Data is cached to data/SYMBOL_INTERVAL.csv — subsequent runs read from disk without hitting the API
- After fetching, report the number of bars fetched and the date range covered
- If the symbol or interval is invalid or the fetch fails, show the error clearly and suggest corrections
