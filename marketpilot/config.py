from dataclasses import dataclass
import math
import os
import re
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    mode: str
    symbols: tuple[str, ...]
    database: str
    paper_orders_enabled: bool
    alpaca_key: str | None
    alpaca_secret: str | None
    max_order_quantity: int
    max_order_notional: float
    max_open_positions: int
    max_symbol_allocation: float
    max_daily_loss: float
    max_data_age_days: int


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _positive_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be positive and finite") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite")
    return value


def load_settings() -> Settings:
    mode = os.getenv("MARKETPILOT_MODE", "paper").strip().lower()
    if mode != "paper":
        raise ValueError("Only MARKETPILOT_MODE=paper is supported")
    symbols = tuple(s.strip().upper() for s in os.getenv("MARKETPILOT_SYMBOLS", "AAPL,MSFT,SPY").split(",") if s.strip())
    if not symbols or len(set(symbols)) != len(symbols) or any(not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", s) for s in symbols):
        raise ValueError("Invalid symbols configuration")
    key = os.getenv("ALPACA_PAPER_API_KEY", "").strip() or None
    secret = os.getenv("ALPACA_PAPER_API_SECRET", "").strip() or None
    if bool(key) != bool(secret):
        raise ValueError("Set both paper credential variables or neither")
    order_flag = os.getenv("MARKETPILOT_PAPER_ORDERS_ENABLED", "false").strip().lower()
    if order_flag not in {"true", "false"}:
        raise ValueError("MARKETPILOT_PAPER_ORDERS_ENABLED must be true or false")
    enabled = order_flag == "true"
    if enabled and not key:
        raise ValueError("Paper orders require paper API credentials")
    allocation = _positive_float("MARKETPILOT_MAX_SYMBOL_ALLOCATION", 0.20)
    if allocation > 1:
        raise ValueError("MARKETPILOT_MAX_SYMBOL_ALLOCATION must be between 0 and 1")
    return Settings(
        mode="paper", symbols=symbols,
        database=os.getenv("MARKETPILOT_DATABASE", "marketpilot.sqlite3"),
        paper_orders_enabled=enabled, alpaca_key=key, alpaca_secret=secret,
        max_order_quantity=_positive_int("MARKETPILOT_MAX_ORDER_QUANTITY", 10),
        max_order_notional=_positive_float("MARKETPILOT_MAX_ORDER_NOTIONAL", 2_000.0),
        max_open_positions=_positive_int("MARKETPILOT_MAX_OPEN_POSITIONS", 5),
        max_symbol_allocation=allocation,
        max_daily_loss=_positive_float("MARKETPILOT_MAX_DAILY_LOSS", 1_000.0),
        max_data_age_days=_positive_int("MARKETPILOT_MAX_DATA_AGE_DAYS", 5),
    )
