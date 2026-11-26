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


def test_risk_limits_can_be_configured(monkeypatch):
    monkeypatch.setenv("MARKETPILOT_MODE", "paper")
    monkeypatch.setenv("MARKETPILOT_MAX_ORDER_QUANTITY", "4")
    monkeypatch.setenv("MARKETPILOT_MAX_SYMBOL_ALLOCATION", "0.15")
    settings = load_settings()
    assert settings.max_order_quantity == 4
    assert settings.max_symbol_allocation == 0.15


def test_symbol_allocation_above_full_equity_is_rejected(monkeypatch):
    monkeypatch.setenv("MARKETPILOT_MODE", "paper")
    monkeypatch.setenv("MARKETPILOT_MAX_SYMBOL_ALLOCATION", "1.1")
    with pytest.raises(ValueError, match="between 0 and 1"):
        load_settings()
