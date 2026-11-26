from datetime import datetime, timedelta, timezone

import pytest
from marketpilot.data import validate_bars
from marketpilot.scheduler import NEW_YORK, next_run
from marketpilot.strategy import Bar


def test_stale_daily_data_is_rejected():
    bar=Bar("AAPL",datetime(2025,1,1,tzinfo=timezone.utc),100)
    with pytest.raises(ValueError,match="stale"):
        validate_bars([bar],now=datetime(2025,1,10,tzinfo=timezone.utc))


def test_future_and_non_finite_bars_are_rejected():
    now=datetime(2025,1,1,tzinfo=timezone.utc)
    with pytest.raises(ValueError,match="future"):
        validate_bars([Bar("AAPL",now+timedelta(days=1),100)],now=now)
    with pytest.raises(ValueError,match="completed"):
        validate_bars([Bar("AAPL",now,float("nan"))],now=now)


def test_schedule_uses_new_york_close_and_skips_weekend():
    friday=datetime(2025,1,3,17,0,tzinfo=NEW_YORK)
    scheduled=next_run(friday)
    assert scheduled.weekday()==0
    assert scheduled.hour==16 and scheduled.minute==15
