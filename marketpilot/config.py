from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    mode: str
    symbols: tuple[str, ...]
    database: str
    paper_orders_enabled: bool
    alpaca_key: str | None
    alpaca_secret: str | None


def load_settings() -> Settings:
    mode = os.getenv("MARKETPILOT_MODE", "paper").strip().lower()
    if mode != "paper":
        raise ValueError("Only MARKETPILOT_MODE=paper is supported")
    symbols = tuple(s.strip().upper() for s in os.getenv("MARKETPILOT_SYMBOLS", "AAPL,MSFT,SPY").split(",") if s.strip())
    if not symbols or any(not s.isascii() or not s.replace(".", "").replace("-", "").isalnum() or len(s) > 10 for s in symbols):
        raise ValueError("Invalid symbols configuration")
    key, secret = os.getenv("ALPACA_PAPER_API_KEY"), os.getenv("ALPACA_PAPER_API_SECRET")
    if bool(key) != bool(secret):
        raise ValueError("Set both paper credential variables or neither")
    enabled = os.getenv("MARKETPILOT_PAPER_ORDERS_ENABLED", "false").lower() == "true"
    if enabled and not key:
        raise ValueError("Paper orders require paper API credentials")
    return Settings("paper", symbols, os.getenv("MARKETPILOT_DATABASE", "marketpilot.sqlite3"), enabled, key, secret)
