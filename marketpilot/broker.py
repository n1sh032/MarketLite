from __future__ import annotations

import httpx
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from .strategy import Bar

PAPER_URL = "https://paper-api.alpaca.markets"
DATA_URL = "https://data.alpaca.markets"


class BrokerError(RuntimeError):
    def __init__(self, message: str, *, uncertain: bool = False):
        super().__init__(message)
        self.uncertain = uncertain


class AlpacaPaperBroker:
    """Alpaca adapter with a hard-coded paper-only trading origin."""
    def __init__(self, key: str, secret: str, timeout: float = 8.0):
        if not key or not secret or key == "replace_me" or secret == "replace_me":
            raise ValueError("Paper API credentials are required")
        self.client = httpx.Client(base_url=PAPER_URL, timeout=timeout, headers={
            "APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret,
        })
        self.data_client = httpx.Client(base_url=DATA_URL, timeout=timeout, headers={
            "APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret,
        })

    def _get(self, path: str) -> dict | list:
        error = None
        for attempt in range(3):
            try:
                response = self.client.get(path)
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500 and exc.response.status_code != 429:
                    raise BrokerError("Paper broker rejected the request") from None
                error = exc
                if attempt < 2:
                    import time
                    time.sleep(0.2 * (2 ** attempt))
        raise BrokerError("Paper broker is unavailable") from error

    def account(self) -> dict:
        data = self._get("/v2/account")
        if not isinstance(data, dict): raise BrokerError("Unexpected account response")
        return data

    def positions(self) -> list:
        data = self._get("/v2/positions")
        if not isinstance(data, list): raise BrokerError("Unexpected positions response")
        return data

    def orders(self) -> list:
        data = self._get("/v2/orders?status=all&limit=100&direction=desc")
        if not isinstance(data, list): raise BrokerError("Unexpected orders response")
        return data

    def daily_bars(self, symbol: str, limit: int = 100, *, now: datetime | None = None) -> list[Bar]:
        ny = ZoneInfo("America/New_York")
        now_ny = now.astimezone(ny) if now else datetime.now(ny)
        market_date = now_ny.date()
        # Include today's daily bar only after the regular session close.
        end = market_date + timedelta(days=1) if now_ny.hour >= 16 else market_date
        cutoff = datetime.combine(end, datetime.min.time(), ny) - timedelta(microseconds=1)
        params = {
            "timeframe": "1Day", "start": (end - timedelta(days=limit * 2)).isoformat(),
            "end": min(now_ny, cutoff).isoformat(), "limit": limit, "sort": "desc",
            "adjustment": "split", "feed": "iex",
        }
        error = None
        for attempt in range(3):
            try:
                response = self.data_client.get(f"/v2/stocks/{symbol}/bars", params=params)
                response.raise_for_status()
                values = response.json().get("bars", [])
                bars = [Bar(symbol.upper(), datetime.fromisoformat(item["t"].replace("Z", "+00:00")), float(item["c"])) for item in values]
                completed = [bar for bar in bars if bar.timestamp.astimezone(ny).date() < end]
                return sorted(completed, key=lambda bar: bar.timestamp)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500 and exc.response.status_code != 429:
                    raise BrokerError("Paper market data request was rejected") from None
                error = exc
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                error = exc
            except (ValueError, KeyError, AttributeError, TypeError):
                raise BrokerError("Paper market data response was invalid") from None
            if attempt < 2:
                import time
                time.sleep(0.2 * (2 ** attempt))
        raise BrokerError("Paper market data is unavailable") from error

    def submit_order(self, *, symbol: str, side: str, quantity: int, client_order_id: str) -> dict:
        try:
            response = self.client.post("/v2/orders", json={
                "symbol": symbol, "qty": str(quantity), "side": side,
                "type": "market", "time_in_force": "day",
                "client_order_id": client_order_id,
            })
            response.raise_for_status()
            order = response.json()
            if not isinstance(order, dict) or not order.get("id") or not order.get("status"):
                raise BrokerError("Incomplete order acknowledgment", uncertain=True)
            return order
        except (ValueError, httpx.TransportError):
            # Do not retry: broker acceptance may have happened before the timeout.
            raise BrokerError("Order outcome is uncertain; reconcile by client order ID before retrying", uncertain=True) from None
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status >= 500 or status == 408:
                raise BrokerError(f"Order outcome is uncertain ({status})", uncertain=True) from None
            raise BrokerError(f"Paper broker rejected the order ({status})") from None

    def close(self) -> None:
        self.client.close()
        self.data_client.close()


class DemoBroker:
    """Clearly labeled local-only account; it never sends network orders."""
    label = "DEMO DATA — simulated $100,000 account"
    def account(self) -> dict:
        return {"equity": "100000.00", "cash": "100000.00", "currency": "USD", "status": "DEMO"}
    def positions(self) -> list:
        return []
    def daily_bars(self, symbol: str, limit: int = 100) -> list[Bar]:
        return []
    def orders(self) -> list:
        return []
    def close(self) -> None:
        pass
