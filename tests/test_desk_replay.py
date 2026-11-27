from datetime import datetime
from dataclasses import replace

import pytest

from marketpilot.desk_replay import NY, Session, replay
from marketpilot.risk import RiskLimits
from marketpilot.strategy import Bar


def sessions(symbol):
    return [Session(Bar(symbol, datetime(2025, 1, day, tzinfo=NY), close), opening, dividend)
            for day, opening, close, dividend in [(2, 10, 10, 0), (3, 20, 22, 1), (6, 22, 25, 1)]]


def test_next_open_dividend_entitlement_and_shared_position_limit():
    book = {s: sessions(s) for s in ("AAPL", "MSFT")}
    limits = replace(RiskLimits(), max_positions=1)
    result = replay(book, 2025, "hold", capital=1000, cost_bps=10, limits=limits)
    assert result["cash"] == pytest.approx(980.98)
    assert result["equity"] == pytest.approx(1005.98)
    assert result["dividends"] == 1
    assert result["fills"] == 1
    assert result["rejection_reasons"] == {"Maximum open positions reached": 1}


def test_fill_gap_cannot_overdraw_cash():
    limits = replace(RiskLimits(), max_symbol_allocation=1)
    result = replay({"SPY": sessions("SPY")}, 2025, "hold", capital=15, limits=limits)
    assert result["cash"] == 15
    assert result["fills"] == 0
    assert result["rejection_reasons"] == {"Insufficient cash at fill": 1}
