from marketpilot.storage import Store


def test_duplicate_signal_and_order_are_idempotent(tmp_path):
    store=Store(tmp_path/"test.sqlite3")
    signal={"symbol":"AAPL","action":"hold","timestamp":"2025-01-01T00:00:00+00:00"}
    store.record_signal(signal);store.record_signal(signal)
    store.record_order("once","AAPL","buy",1,"accepted")
    store.record_order("once","AAPL","buy",1,"accepted")
    assert len(store.rows("signals"))==1
    assert len(store.rows("orders"))==1
    store.audit("risk_decision",{"approved":False})
    assert store.rows("audit")[0]["event"]=="risk_decision"
    store.close()
