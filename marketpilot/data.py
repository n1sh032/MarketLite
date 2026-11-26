from datetime import datetime, timedelta, timezone
import math

from .strategy import Bar


def demo_bars(symbol: str, count: int = 80) -> list[Bar]:
    """Deterministic illustrative closes. Not exchange data."""
    today = datetime.now(timezone.utc).date()
    bars = []
    day = today
    while len(bars) < count:
        if day.weekday() < 5:
            index = len(bars)
            close = 100 + index * 0.12 + 4 * math.sin(index / 7)
            bars.append(Bar(symbol.upper(), datetime.combine(day, datetime.min.time(), timezone.utc), close))
        day -= timedelta(days=1)
    return list(reversed(bars))


def validate_bars(bars: list[Bar], *, max_age_days: int = 5, now: datetime | None = None) -> None:
    if not bars:
        raise ValueError("No market bars returned")
    latest = max(bar.timestamp for bar in bars)
    now = now or datetime.now(timezone.utc)
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    if (now - latest).total_seconds() > max_age_days * 86400:
        raise ValueError("Market data is stale")
    dates = [bar.timestamp.date() for bar in bars]
    if len(dates) != len(set(dates)):
        raise ValueError("Duplicate daily bars returned")
    if any(not bar.complete or not math.isfinite(bar.close) or bar.close <= 0 for bar in bars):
        raise ValueError("Bars must be completed with positive closes")
