# MarketPilot

MarketPilot is a local-first research dashboard for explainable US stock signals and paper account monitoring. It is an educational project; signals are not predictions or investment advice, and no strategy is claimed to make money.

## Run locally

Requires Python 3.11 or newer.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
uvicorn marketpilot.app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. The app binds to localhost by default. Run tests with `python -m pytest`.

## Modes

By default MarketPilot runs without credentials using deterministic illustrative daily bars and a simulated $100,000 account. The dashboard labels these values as demo data; they are not exchange data or a real account balance. The demo broker has no order submission method.

To connect a paper account, set `ALPACA_PAPER_API_KEY` and `ALPACA_PAPER_API_SECRET` in the process environment. They are placeholders in `.env.example`; never commit real values. The trading adapter hard-codes Alpaca's `https://paper-api.alpaca.markets` origin and rejects incomplete credentials. It fetches daily bars from Alpaca's market data API using the IEX feed and includes the current New York date only after 16:00 local time, and skips it beforehand to avoid using an incomplete daily bar. Read-only account/position/order reconciliation runs at startup. Failures block order submission.

Paper order submission is disabled unless `MARKETPILOT_PAPER_ORDERS_ENABLED=true` is explicitly configured. The API additionally requires a confirmed paper-order request. The dashboard's Run Analysis button only calculates and stores signals; it never submits orders. Order submission is an API capability for deliberate, confirmed paper workflows. The app does not accept a configurable broker URL, and there is no live trading mode.

Paper execution is simulated and does not reproduce live fills, liquidity, market impact, or queue position. API keys are not stored by MarketPilot; provide them through environment variables. Do not share the localhost service with untrusted users.

## Strategy and controls

The example strategy is a 20-day/50-day simple moving-average crossover on completed daily close prices. It reports buy, sell, or hold, both averages, parameters, timestamp, and a short reason. It emits hold until enough bars exist. Strategy code has no broker dependency.

Risk assessment is a separate required function and checks symbol allow-list, quantity, notional, position count, allocation, daily loss, stale data, and duplicate orders. Risk decisions and control actions are written to SQLite. SQLite uses WAL mode; `marketpilot.sqlite3` is local state and is excluded from Git. Analysis is idempotent by symbol and input timestamp. A unique client order ID and broker order lookup help prevent duplicate submissions after a restart. Ambiguous order timeouts are never retried blindly.

Configuration lives in the ignored local `.env` file or process environment. `MARKETPILOT_MODE` must be `paper`; `MARKETPILOT_SYMBOLS` sets the allow-listed universe; `MARKETPILOT_PAPER_ORDERS_ENABLED` defaults to false. The `MARKETPILOT_MAX_ORDER_QUANTITY`, `MARKETPILOT_MAX_ORDER_NOTIONAL`, `MARKETPILOT_MAX_OPEN_POSITIONS`, `MARKETPILOT_MAX_SYMBOL_ALLOCATION`, `MARKETPILOT_MAX_DAILY_LOSS`, and `MARKETPILOT_MAX_DATA_AGE_DAYS` values configure the independent risk limits. Invalid or non-finite limits fail at startup.

## Project layout

- `data.py`: demo bars and stale/completeness validation
- `strategy.py`: pure moving-average signal calculation
- `risk.py`: independent order approval decision
- `broker.py`: demo and fixed-origin Alpaca paper adapters
- `storage.py`: SQLite signals, order intents, broker reconciliation, and audit events
- `app.py`: FastAPI endpoints, reconciliation, and lifecycle
- `static/`: responsive local dashboard
- `tests/`: focused strategy, risk, and storage tests

## Current limits

The dashboard uses polling rather than a streaming feed. An in-process scheduler runs analysis at 16:15 America/New_York on weekdays; it does not submit orders. It does not yet load an exchange holiday calendar, so a holiday run may reuse the latest available completed bar. You can also use Run Analysis manually. The initial version supports daily bars and a small configured universe. Account and positions are refreshed from Alpaca when the dashboard loads; broker responses refresh any matching local order intents. No account identifiers or secrets are displayed or persisted. The automated suite has been run locally; live Alpaca behavior has not been verified. Before enabling paper orders, inspect the paper account and API permissions and validate reconciliation against that paper account. There is no live trading capability.
