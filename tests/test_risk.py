from marketpilot.risk import RiskLimits, assess_order


def assess(**kwargs):
    defaults=dict(symbol="AAPL",side="buy",quantity=1,price=100,limits=RiskLimits())
    defaults.update(kwargs)
    return assess_order(**defaults)


def test_allowed_order_passes():
    assert assess().approved


def test_disallowed_symbol_is_rejected():
    decision=assess(symbol="GME")
    assert not decision.approved and "allow-listed" in decision.reasons[0]


def test_quantity_and_notional_are_bounded():
    decision=assess(quantity=11,price=300)
    assert not decision.approved
    assert len(decision.reasons)>=2


def test_stale_and_duplicate_orders_fail_closed():
    decision=assess(stale=True,duplicate=True)
    assert not decision.approved
    assert len(decision.reasons)==2


def test_daily_loss_blocks_new_order():
    assert not assess(daily_pnl=-1000).approved


def test_sell_cannot_exceed_held_quantity():
    decision=assess(side="sell",quantity=2,held_quantity=1)
    assert not decision.approved
    assert "Sell quantity exceeds held shares" in decision.reasons
