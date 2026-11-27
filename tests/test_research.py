from datetime import datetime, timezone

import pytest

from marketpilot.research import evaluate, targets
from marketpilot.strategy import Bar


def bar(month, day, close):
    return Bar("TEST", datetime(2020, month, day, tzinfo=timezone.utc), close)


def test_monthly_trade_pays_cost_and_cannot_capture_execution_day_jump():
    bars = [bar(1, 31, 10), bar(2, 28, 20), bar(3, 2, 40), bar(3, 3, 44)]
    assert list(targets(bars, 2, 2020)) == [0, 0, 1, 1]
    growth, drawdown, _, trades = evaluate(bars, 2, 2020, 2020, 5)
    assert (1 + growth) ** (4 / 252) == pytest.approx(0.9995 * 1.1)
    assert drawdown == pytest.approx(-0.0005)
    assert trades == 1


def test_future_prices_do_not_change_earlier_positions():
    bars = [bar(1, 31, 10), bar(2, 28, 20), bar(3, 2, 40)]
    extended = bars + [bar(3, 31, 1), bar(4, 1, 5)]
    assert list(targets(extended, 2, 2020))[:3] == list(targets(bars, 2, 2020))
