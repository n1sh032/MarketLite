from dataclasses import dataclass
from datetime import datetime
from typing import Sequence


@dataclass(frozen=True)
class Bar:
    symbol: str
    timestamp: datetime
    close: float
    complete: bool = True


@dataclass(frozen=True)
class Signal:
    symbol: str
    action: str
    timestamp: datetime
    fast_sma: float | None
    slow_sma: float | None
    reason: str
    fast_window: int = 20
    slow_window: int = 50


def moving_average_signal(bars: Sequence[Bar], fast: int = 20, slow: int = 50) -> Signal:
    if fast < 1 or slow <= fast:
        raise ValueError("Windows must satisfy 1 <= fast < slow")
    ordered = sorted((b for b in bars if b.complete), key=lambda b: b.timestamp)
    if not ordered:
        raise ValueError("No completed bars supplied")
    symbol = ordered[-1].symbol.upper()
    if any(b.symbol.upper() != symbol for b in ordered):
        raise ValueError("Bars must contain one symbol")
    if len(ordered) < slow + 1:
        return Signal(symbol, "hold", ordered[-1].timestamp, None, None,
                      f"Need {slow + 1} completed bars; received {len(ordered)}", fast, slow)
    closes = [b.close for b in ordered]
    if any(price <= 0 for price in closes):
        raise ValueError("Closing prices must be positive")
    fast_prev = sum(closes[-fast-1:-1]) / fast
    slow_prev = sum(closes[-slow-1:-1]) / slow
    fast_now = sum(closes[-fast:]) / fast
    slow_now = sum(closes[-slow:]) / slow
    action = "hold"
    if fast_prev <= slow_prev and fast_now > slow_now:
        action = "buy"
    elif fast_prev >= slow_prev and fast_now < slow_now:
        action = "sell"
    reason = f"SMA{fast} {fast_now:.2f} vs SMA{slow} {slow_now:.2f}; prior {fast_prev:.2f} vs {slow_prev:.2f}"
    return Signal(symbol, action, ordered[-1].timestamp, fast_now, slow_now, reason, fast, slow)
