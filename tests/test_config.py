import pytest
from marketpilot.config import load_settings


def test_live_mode_is_rejected(monkeypatch):
    monkeypatch.setenv("MARKETPILOT_MODE","live")
    with pytest.raises(ValueError,match="Only MARKETPILOT_MODE=paper"):
        load_settings()


def test_order_flag_needs_paper_credentials(monkeypatch):
    monkeypatch.setenv("MARKETPILOT_MODE","paper")
    monkeypatch.setenv("MARKETPILOT_PAPER_ORDERS_ENABLED","true")
    monkeypatch.delenv("ALPACA_PAPER_API_KEY",raising=False)
    monkeypatch.delenv("ALPACA_PAPER_API_SECRET",raising=False)
    with pytest.raises(ValueError,match="require paper API credentials"):
        load_settings()
