import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Event

import pytest
from fastapi import HTTPException

from marketpilot import app as desk
from marketpilot.broker import BrokerError
from marketpilot.storage import Store
from marketpilot.strategy import Bar


class PaperAccount:
    def __init__(self):
        self.submissions = 0
        self.history = []
        self.outcome = "accepted"

    def daily_bars(self, symbol):
        today = datetime.now(timezone.utc) - timedelta(hours=1)
        return [Bar(symbol, today - timedelta(days=50-i), 101 if i == 50 else 100)
                for i in range(51)]

    def account(self):
        return {"equity": "10000", "last_equity": "10000"}

    def positions(self):
        return []

    def orders(self):
        return self.history.copy()

    def submit_order(self, **intent):
        self.submissions += 1
        if self.outcome == "rejected":
            raise BrokerError("Rejected")
        order = dict(intent, id="paper-1", status="accepted")
        self.history.append(order)
        if self.outcome == "timeout":
            raise BrokerError("Acknowledgment lost", uncertain=True)
        return order


@pytest.fixture
def paper(monkeypatch, tmp_path):
    account = PaperAccount()
    monkeypatch.setattr(desk, "broker", account)
    monkeypatch.setattr(desk, "settings", replace(desk.settings, symbols=("AAPL",), paper_orders_enabled=True))
    monkeypatch.setattr(desk, "store", Store(tmp_path / "desk.db"))
    monkeypatch.setattr(desk, "state", dict(desk.state, paused=False, emergency_stop=False, reconciled=True))
    yield account
    desk.store.close()


def run():
    return desk.run_analysis(desk.RunRequest(submit_paper_orders=True, confirmed=True))


def test_stop_during_portfolio_read(paper, monkeypatch):
    entered, release = Event(), Event()

    def slow_positions():
        entered.set()
        assert release.wait(5)
        return []

    monkeypatch.setattr(paper, "positions", slow_positions)

    async def scenario():
        task = asyncio.create_task(run())
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            await desk.emergency_stop()
        finally:
            release.set()
        with pytest.raises(HTTPException) as err:
            await task
        assert err.value.status_code == 409

    asyncio.run(scenario())
    assert paper.submissions == 0
    assert desk.store.rows("orders") == []


@pytest.mark.parametrize("outcome,initial", [("accepted","accepted"), ("rejected","rejected"), ("timeout","submitting")])
def test_restart_never_resubmits(paper, tmp_path, outcome, initial):
    paper.outcome = outcome
    asyncio.run(run())
    assert desk.store.rows("orders")[0]["status"] == initial
    desk.store.close()
    desk.store = Store(tmp_path / "desk.db")
    if paper.history:
        paper.history[0].update(status="filled", filled_qty="1")
    desk.reconcile_paper_state()
    assert desk.store.rows("orders")[0]["status"] == ("filled" if paper.history else "rejected")
    result = asyncio.run(run())
    assert not result["signals"][0]["risk"]["approved"]
    assert paper.submissions == 1


def test_browser_controls_require_local_json(paper):
    import httpx

    async def scenario():
        transport = httpx.ASGITransport(app=desk.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            foreign = await client.post("/api/pause", json={}, headers={"Origin": "https://example.org"})
            assert foreign.status_code == 403
            form = await client.post("/api/pause", data={"toggle": "1"})
            assert form.status_code == 415
            assert not desk.state["paused"]
            local = await client.post("/api/pause", json={}, headers={"Origin": "http://localhost"})
            assert local.json()["paused"]
            dashboard = (await client.get("/api/dashboard")).json()
            assert dashboard["paper"]
            assert dashboard["exposure"] == 0
    asyncio.run(scenario())
