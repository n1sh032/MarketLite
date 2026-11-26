from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .broker import AlpacaPaperBroker, BrokerError, DemoBroker
from .config import load_settings
from .data import demo_bars, validate_bars
from .risk import RiskLimits, assess_order
from .storage import Store
from .scheduler import next_run, run_daily
from .strategy import moving_average_signal

settings = load_settings()
store = Store(settings.database)
broker = AlpacaPaperBroker(settings.alpaca_key, settings.alpaca_secret) if settings.alpaca_key and settings.alpaca_secret else DemoBroker()
state = {"status": "stopped", "paused": False, "emergency_stop": False, "last_run": None, "last_error": None, "reconciled": isinstance(broker, DemoBroker)}
run_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not isinstance(broker, DemoBroker):
        try:
            # Read broker state before any order endpoint can be enabled.
            broker.account(); broker.positions(); broker.orders()
            state["reconciled"] = True
            store.audit("broker_reconciled", {"mode": "paper"})
        except BrokerError as exc:
            state["last_error"] = str(exc)
            state["reconciled"] = False
    scheduler_task = asyncio.create_task(run_daily(scheduled_analysis), name="marketpilot-daily-analysis")
    state["next_scheduled_run"] = next_run().isoformat()
    try:
        yield
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        broker.close()
        store.close()


app = FastAPI(title="MarketPilot", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


class RunRequest(BaseModel):
    submit_paper_orders: bool = False
    confirmed: bool = False


@app.get("/")
def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/dashboard")
def dashboard():
    try:
        account = broker.account()
        positions = broker.positions()
        orders = broker.orders()
    except BrokerError as exc:
        state["last_error"] = str(exc)
        account, positions, orders = None, [], store.rows("orders")
    local_orders = store.rows("orders")
    known = {o.get("client_order_id") for o in orders} if isinstance(orders, list) else set()
    visible_orders = orders + [o for o in local_orders if o.get("client_order_id") not in known] if isinstance(orders, list) else local_orders
    return {"paper": True, "demo": isinstance(broker, DemoBroker), "demo_label": getattr(broker, "label", None),
            "account": account, "positions": positions, "signals": store.rows("signals"), "orders": visible_orders,
            "audit": store.rows("audit", 30), "symbols": settings.symbols,
            "limits": {"max_quantity": 10, "max_notional": 2000, "max_positions": 5, "max_daily_loss": 1000},
            "state": state}


@app.post("/api/run")
async def run_analysis(request: RunRequest):
    if state["paused"] or state["emergency_stop"]:
        raise HTTPException(409, "Analysis is paused or emergency stop is active")
    if request.submit_paper_orders and (not request.confirmed or not settings.paper_orders_enabled):
        raise HTTPException(403, "Paper orders require explicit confirmation and MARKETPILOT_PAPER_ORDERS_ENABLED=true")
    if request.submit_paper_orders and (isinstance(broker, DemoBroker) or not state["reconciled"]):
        raise HTTPException(503, "Paper broker is not reconciled; order submission is disabled")
    async with run_lock:
        state["status"] = "running"
        state["last_error"] = None
        results = []
        try:
            for symbol in settings.symbols:
                bars = demo_bars(symbol) if isinstance(broker, DemoBroker) else broker.daily_bars(symbol)
                validate_bars(bars)
                signal = moving_average_signal(bars)
                payload = {**signal.__dict__, "timestamp": signal.timestamp.isoformat(), "data_source": "illustrative demo bars" if isinstance(broker, DemoBroker) else "Alpaca IEX daily bars"}
                store.record_signal(payload)
                item = {**payload, "risk": None, "order": None}
                if request.submit_paper_orders and signal.action in {"buy", "sell"}:
                    account = broker.account(); positions = broker.positions(); existing = broker.orders()
                    qty = 1
                    position = next((p for p in positions if p.get("symbol") == symbol), None)
                    market_value = abs(float(position.get("market_value", 0))) if position else 0.0
                    if "equity" not in account or "last_equity" not in account:
                        raise ValueError("Broker account equity is incomplete; refusing paper order")
                    daily_pnl = float(account["equity"]) - float(account["last_equity"])
                    client_id = f"mp-{symbol}-{signal.timestamp:%Y%m%d}-{signal.action}"
                    duplicate = store.has_order(client_id) or any(o.get("client_order_id") == client_id for o in existing)
                    decision = assess_order(symbol=symbol, side=signal.action, quantity=qty, price=bars[-1].close,
                        limits=RiskLimits(allowed_symbols=frozenset(settings.symbols)), open_positions=len(positions), current_symbol_value=market_value,
                        equity=float(account["equity"]), daily_pnl=daily_pnl, duplicate=duplicate,
                        held_quantity=int(float(position.get("qty", 0))) if position else 0)
                    item["risk"] = {"approved": decision.approved, "reasons": decision.reasons}
                    store.audit("risk_decision", {"symbol":symbol,"approved":decision.approved,"reasons":decision.reasons})
                    if decision.approved:
                        store.record_order(client_id,symbol,signal.action,qty,"submitting")
                        try:
                            order = broker.submit_order(symbol=symbol,side=signal.action,quantity=qty,client_order_id=client_id)
                            store.record_order(client_id,symbol,signal.action,qty,str(order.get("status","accepted")),str(order.get("id","")),order)
                            item["order"] = order
                        except BrokerError as exc:
                            store.audit("order_uncertain_or_rejected", {"client_order_id":client_id,"message":str(exc)})
                            state["last_error"] = str(exc)
                results.append(item)
            state["last_run"] = datetime.now(timezone.utc).isoformat()
            state["status"] = "paused" if state["paused"] else "stopped"
            store.audit("analysis_completed", {"count":len(results)})
            return {"signals":results}
        except (ValueError, BrokerError) as exc:
            state["status"] = "error"; state["last_error"] = str(exc)
            store.audit("analysis_error", {"message":str(exc)})
            raise HTTPException(503, str(exc)) from None


async def scheduled_analysis():
    try:
        await run_analysis(RunRequest())
        state["scheduler_error"] = None
    except HTTPException as exc:
        state["scheduler_error"] = exc.detail
        store.audit("scheduler_error", {"message":exc.detail})
    state["next_scheduled_run"] = next_run().isoformat()


@app.post("/api/pause")
def pause():
    state["paused"] = not state["paused"]
    state["status"] = "paused" if state["paused"] else "stopped"
    store.audit("pause_changed", {"paused":state["paused"]})
    return state


@app.post("/api/emergency-stop")
def emergency_stop():
    state["emergency_stop"] = True; state["status"] = "stopped"
    store.audit("emergency_stop", {"active":True})
    return state
