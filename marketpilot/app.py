from __future__ import annotations

import asyncio
import math
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
from .storage import Store, TERMINAL_ORDER_STATUSES
from .scheduler import next_run, run_daily
from .strategy import moving_average_signal

settings = load_settings()
store = Store(settings.database)
broker = AlpacaPaperBroker(settings.alpaca_key, settings.alpaca_secret) if settings.alpaca_key and settings.alpaca_secret else DemoBroker()
risk_limits = RiskLimits(
    allowed_symbols=frozenset(settings.symbols),
    max_quantity=settings.max_order_quantity,
    max_notional=settings.max_order_notional,
    max_positions=settings.max_open_positions,
    max_symbol_allocation=settings.max_symbol_allocation,
    max_daily_loss=settings.max_daily_loss,
)
last_successful_run = store.latest_event_at("analysis_completed")
if last_successful_run:
    restored_time = datetime.fromisoformat(last_successful_run)
    if restored_time.tzinfo is None:
        restored_time = restored_time.replace(tzinfo=timezone.utc)
    last_successful_run = restored_time.isoformat()
state = {"status": "stopped", "paused": False, "emergency_stop": False,
         "last_data_refresh": last_successful_run, "last_run": last_successful_run,
         "last_error": None, "broker_error": None,
         "reconciled": isinstance(broker, DemoBroker)}
run_lock = asyncio.Lock()


def reconcile_paper_state():
    account = broker.account()
    positions = broker.positions()
    orders = broker.orders()
    if not isinstance(broker, DemoBroker):
        refreshed = store.reconcile_orders(orders)
        store.audit("broker_reconciled", {"mode": "paper", "orders_refreshed": refreshed})
    state["reconciled"] = True
    state["broker_error"] = None
    return account, positions, orders


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not isinstance(broker, DemoBroker):
        try:
            reconcile_paper_state()
        except BrokerError as exc:
            state["broker_error"] = str(exc)
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
        account, positions, orders = reconcile_paper_state()
    except BrokerError as exc:
        state["broker_error"] = str(exc)
        state["reconciled"] = isinstance(broker, DemoBroker)
        account, positions, orders = None, [], store.rows("orders")
    local_orders = store.rows("orders")
    known = {o.get("client_order_id") for o in orders} if isinstance(orders, list) else set()
    visible_orders = orders + [o for o in local_orders if o.get("client_order_id") not in known] if isinstance(orders, list) else local_orders
    try:
        market_values = [float(position["market_value"]) for position in positions]
        exposure = sum(abs(value) for value in market_values) if all(math.isfinite(value) for value in market_values) else None
    except (KeyError, TypeError, ValueError):
        exposure = None
    return {"paper": True, "demo": isinstance(broker, DemoBroker), "demo_label": getattr(broker, "label", None),
            "account": account, "positions": positions, "signals": store.signals(), "orders": visible_orders,
            "exposure": exposure,
            "audit": store.rows("audit", 30), "symbols": settings.symbols,
            "limits": {"max_quantity": risk_limits.max_quantity,
                       "max_notional": risk_limits.max_notional,
                       "max_positions": risk_limits.max_positions,
                       "max_symbol_allocation": risk_limits.max_symbol_allocation,
                       "max_daily_loss": risk_limits.max_daily_loss,
                       "max_data_age_days": settings.max_data_age_days},
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
                bars = demo_bars(symbol) if isinstance(broker, DemoBroker) else await asyncio.to_thread(broker.daily_bars, symbol)
                validate_bars(bars, max_age_days=settings.max_data_age_days)
                signal = moving_average_signal(bars)
                payload = {**signal.__dict__, "timestamp": signal.timestamp.isoformat(), "data_source": "illustrative demo bars" if isinstance(broker, DemoBroker) else "Alpaca IEX daily bars"}
                store.record_signal(payload)
                item = {**payload, "risk": None, "order": None}
                if request.submit_paper_orders and signal.action in {"buy", "sell"}:
                    account = await asyncio.to_thread(broker.account)
                    positions = await asyncio.to_thread(broker.positions)
                    existing = await asyncio.to_thread(broker.orders)
                    qty = 1
                    position = next((p for p in positions if p.get("symbol") == symbol), None)
                    market_value = abs(float(position.get("market_value", 0))) if position else 0.0
                    if "equity" not in account or "last_equity" not in account:
                        raise ValueError("Broker account equity is incomplete; refusing paper order")
                    daily_pnl = float(account["equity"]) - float(account["last_equity"])
                    client_id = f"mp-{symbol}-{signal.timestamp:%Y%m%d}-{signal.action}"
                    active_broker_order = any(
                        str(order.get("symbol", "")).upper() == symbol
                        and str(order.get("status", "unknown")).lower() not in TERMINAL_ORDER_STATUSES
                        for order in existing
                    )
                    duplicate = store.has_order(client_id) or store.has_open_order(symbol) or active_broker_order
                    decision = assess_order(symbol=symbol, side=signal.action, quantity=qty, price=bars[-1].close,
                        limits=risk_limits, open_positions=len(positions), current_symbol_value=market_value,
                        equity=float(account["equity"]), daily_pnl=daily_pnl, duplicate=duplicate,
                        held_quantity=int(float(position.get("qty", 0))) if position else 0)
                    item["risk"] = {"approved": decision.approved, "reasons": decision.reasons}
                    store.audit("risk_decision", {"symbol":symbol,"approved":decision.approved,"reasons":decision.reasons})
                    if decision.approved:
                        store.record_order(client_id,symbol,signal.action,qty,"submitting")
                        try:
                            order = await asyncio.to_thread(
                                broker.submit_order, symbol=symbol, side=signal.action,
                                quantity=qty, client_order_id=client_id,
                            )
                            store.record_order(client_id,symbol,signal.action,qty,str(order.get("status","accepted")),str(order.get("id","")),order)
                            item["order"] = order
                        except BrokerError as exc:
                            if not exc.uncertain:
                                store.record_order(client_id, symbol, signal.action, qty, "rejected", payload={"error": str(exc)})
                            store.audit("order_uncertain_or_rejected", {"client_order_id":client_id,"message":str(exc)})
                            state["last_error"] = str(exc)
                results.append(item)
            state["last_run"] = datetime.now(timezone.utc).isoformat()
            state["last_data_refresh"] = state["last_run"]
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
    except Exception as exc:
        message = f"Scheduled run failed ({type(exc).__name__})"
        state["scheduler_error"] = message
        store.audit("scheduler_error", {"message":message})
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
