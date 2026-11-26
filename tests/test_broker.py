import httpx
import pytest

from marketpilot.broker import AlpacaPaperBroker, BrokerError, PAPER_URL


def broker_with(handler):
    broker = AlpacaPaperBroker("paper-key", "paper-secret")
    broker.client.close()
    broker.client = httpx.Client(
        base_url=PAPER_URL,
        transport=httpx.MockTransport(handler),
        headers={"APCA-API-KEY-ID": "paper-key", "APCA-API-SECRET-KEY": "paper-secret"},
    )
    return broker


def test_order_timeout_is_uncertain_and_is_not_retried():
    calls = 0

    def timeout(request):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("simulated timeout")

    broker = broker_with(timeout)
    try:
        with pytest.raises(BrokerError) as error:
            broker.submit_order(symbol="AAPL", side="buy", quantity=1, client_order_id="once")
        assert error.value.uncertain
        assert calls == 1
    finally:
        broker.close()


def test_rejected_order_is_definitive():
    broker = broker_with(lambda request: httpx.Response(403, json={"message": "rejected"}))
    try:
        with pytest.raises(BrokerError, match="403") as error:
            broker.submit_order(symbol="AAPL", side="buy", quantity=1, client_order_id="once")
        assert not error.value.uncertain
    finally:
        broker.close()


def test_read_only_get_retries_temporary_errors():
    calls = 0

    def flaky(request):
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(503, json={"message": "temporary"})
        return httpx.Response(200, json={"equity": "1000"})

    broker = broker_with(flaky)
    try:
        assert broker.account()["equity"] == "1000"
        assert calls == 3
    finally:
        broker.close()
