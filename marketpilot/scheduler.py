import asyncio
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")


def next_run(now: datetime | None = None) -> datetime:
    now = now.astimezone(NEW_YORK) if now else datetime.now(NEW_YORK)
    target = now.replace(hour=16, minute=15, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    while target.weekday() >= 5:
        target += timedelta(days=1)
    return target


async def run_daily(callback) -> None:
    """Call an async analysis callback at 16:15 New York time on weekdays."""
    while True:
        target = next_run()
        await asyncio.sleep(max(0, (target - datetime.now(NEW_YORK)).total_seconds()))
        try:
            await callback()
        except Exception:
            # The owning app records the scheduler failure and continues next day.
            pass
