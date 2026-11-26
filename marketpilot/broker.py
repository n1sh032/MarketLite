from __future__ import annotations

import httpx

PAPER_URL = "https://paper-api.alpaca.markets"
DATA_URL = "https://data.alpaca.markets"


class BrokerError(RuntimeError):
    pass


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

    def submit_order(self, *, symbol: str, side: str, quantity: int, client_order_id: str) -> dict:
        try:
            response = self.client.post("/v2/orders", json={
                "symbol": symbol, "qty": str(quantity), "side": side,
                "type": "market", "time_in_force": "day",
                "client_order_id": client_order_id,
            })
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.NetworkError):
            # Do not retry: broker acceptance may have happened before the timeout.
            raise BrokerError("Order outcome is uncertain; reconcile by client order ID before retrying") from None
        except httpx.HTTPStatusError:
            raise BrokerError("Paper broker rejected the order") from None

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
    def orders(self) -> list:
        return []
    def close(self) -> None:
        pass
