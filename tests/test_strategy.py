from datetime import datetime, timedelta, timezone

import pytest
from marketpilot.strategy import Bar, moving_average_signal


def bars(values):
    start=datetime(2025,1,1,tzinfo=timezone.utc)
    return [Bar("AAPL",start+timedelta(days=i),v) for i,v in enumerate(values)]


def test_holds_until_slow_window_is_available():
    signal=moving_average_signal(bars([100]*50))
    assert signal.action=="hold"
    assert "Need 51" in signal.reason


def test_flat_series_holds():
    assert moving_average_signal(bars([100]*60)).action=="hold"


def test_rejects_invalid_window_order():
    with pytest.raises(ValueError): moving_average_signal(bars([100]*60),50,20)


def test_incomplete_bar_is_ignored():
    values=bars([100]*50)
    values.append(Bar("AAPL",datetime(2025,3,1,tzinfo=timezone.utc),200,False))
    assert moving_average_signal(values).timestamp==values[-2].timestamp


def test_crossing_above_emits_buy():
    signal=moving_average_signal(bars([1,1,1,10]),fast=2,slow=3)
    assert signal.action=="buy"
    assert signal.fast_sma > signal.slow_sma


def test_crossing_below_emits_sell():
    signal=moving_average_signal(bars([10,10,10,1]),fast=2,slow=3)
    assert signal.action=="sell"
    assert signal.fast_sma < signal.slow_sma
