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
    now = now or datetime.now(timezone.utc)
    now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
    timestamps = [bar.timestamp.replace(tzinfo=timezone.utc) if bar.timestamp.tzinfo is None else bar.timestamp.astimezone(timezone.utc) for bar in bars]
    latest = max(timestamps)
    if latest > now:
        raise ValueError("Market data contains a future bar")
    if (now - latest).total_seconds() > max_age_days * 86400:
        raise ValueError("Market data is stale")
    dates = [timestamp.date() for timestamp in timestamps]
    if len(dates) != len(set(dates)):
        raise ValueError("Duplicate daily bars returned")
    if any(not bar.complete or not math.isfinite(bar.close) or bar.close <= 0 for bar in bars):
        raise ValueError("Bars must be completed with positive closes")
