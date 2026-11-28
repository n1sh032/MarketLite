"""Replay a single calendar year with one shared paper account and next-open fills."""
import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from .risk import RiskLimits, assess_order
from .strategy import Bar, moving_average_signal

NY = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class Session:
    bar: Bar
    opening: float
    dividend: float = 0


def history(path, symbol):
    chart = json.loads(path.read_bytes())["chart"]["result"][0]
    if chart["meta"]["symbol"] != symbol or chart["meta"]["currency"] != "USD":
        raise ValueError("Expected the requested USD symbol")
    events = chart.get("events", {})
    if events.get("splits"):
        raise ValueError("Use a split-free interval for one-share accounting")
    dividends = {datetime.fromtimestamp(e["date"], NY).date(): e["amount"]
                 for e in events.get("dividends", {}).values()}
    quote = chart["indicators"]["quote"][0]
    rows = []
    for stamp, opening, close in zip(chart["timestamp"], quote["open"], quote["close"], strict=True):
        if not all(p is not None and math.isfinite(p) and p > 0 for p in (opening, close)):
            raise ValueError("Missing or invalid session price")
        when = datetime.fromtimestamp(stamp, NY)
        rows.append(Session(Bar(symbol, when, close), opening, dividends.get(when.date(), 0)))
    return rows


def replay(series, year, rule="20/50", *, capital=100000, cost_bps=5, limits=None):
    symbols = tuple(series)
    if rule not in {"20/50", "8-month", "hold"} or not symbols or capital <= 0 or not 0 <= cost_bps < 10000:
        raise ValueError("Invalid replay settings")
    limits = limits or RiskLimits(allowed_symbols=frozenset(symbols))
    dates = [s.bar.timestamp.date() for s in series[symbols[0]]]
    if dates != sorted(set(dates)) or any([s.bar.timestamp.date() for s in rows] != dates for rows in series.values()):
        raise ValueError("Expected unique, aligned trading sessions")
    if not any(d.year == year for d in dates):
        raise ValueError("No evaluation sessions")
    cash = equity = peak = capital
    pnl = drawdown = fees = dividends = 0.
    holdings = dict.fromkeys(symbols, 0)
    share_sessions = Counter()
    passive_gain = Counter()
    gross_gain = Counter()
    measured_sessions = 0
    pending = {}
    months = {s: [] for s in symbols}
    rejected = Counter()
    exposure = []
    fills = 0
    for i, day in enumerate(dates):
        if day.year > year:
            break
        month_end = i + 1 < len(dates) and day.month != dates[i+1].month
        if month_end:
            for s in symbols:
                months[s].append(series[s][i].bar.close)
        if day.year != year:
            continue
        previous_equity = equity
        for s in symbols:
            row = series[s][i]
            income = holdings[s] * row.dividend
            cash += income
            dividends += income
            side = pending.get(s)
            if side:
                fee = row.opening * cost_bps / 10000
                if side == "buy" and row.opening + fee > cash:
                    rejected["Insufficient cash at fill"] += 1
                    continue
                delta = 1 if side == "buy" else -1
                holdings[s] += delta
                cash -= delta * row.opening + fee
                fees += fee
                fills += 1
        # Use post-fill holdings for each open-to-open interval. A dividend
        # at the next open belongs to the shares carried into that session.
        if exposure:  # The first eligible fill is on the second session.
            measured_sessions += 1
            for symbol, quantity in holdings.items():
                row = series[symbol][i]
                if i + 1 < len(dates) and dates[i + 1].year == year:
                    following = series[symbol][i + 1]
                    change = following.opening - row.opening + following.dividend
                else:
                    change = row.bar.close - row.opening
                share_sessions[symbol] += quantity
                passive_gain[symbol] += change
                gross_gain[symbol] += quantity * change
        pending.clear()
        invested = sum(holdings[s]*series[s][i].bar.close for s in symbols)
        equity = cash + invested
        pnl = equity - previous_equity
        peak = max(equity, peak)
        drawdown = min(drawdown, equity/peak - 1)
        exposure.append(invested/equity)
        if i + 1 == len(dates) or dates[i+1].year != year:
            continue
        occupied = {s for s in symbols if holdings[s]}
        for s in symbols:
            price = series[s][i].bar.close
            if rule == "20/50":
                window = [r.bar for r in series[s][max(0, i-50):i+1]]
                side = moving_average_signal(window).action
            elif rule == "hold":
                side = "buy" if len(exposure) == 1 else "hold"
            elif month_end and len(months[s]) >= 8:
                target = int(price > sum(months[s][-8:])/8)
                side = "hold" if holdings[s] == target else ("buy" if target else "sell")
            else:
                side = "hold"
            if side == "hold":
                continue
            decision = assess_order(symbol=s, side=side, quantity=1, price=price, limits=limits,
                                    open_positions=len(occupied), current_symbol_value=holdings[s]*price,
                                    equity=equity, daily_pnl=pnl, held_quantity=holdings[s])
            if decision.approved:
                pending[s] = side
                if side == "buy":
                    occupied.add(s)
            else:
                rejected.update(decision.reasons)
    attribution = {}
    for symbol in symbols:
        mean_shares = share_sessions[symbol] / measured_sessions if measured_sessions else 0
        holding_gain = mean_shares * passive_gain[symbol]
        attribution[symbol] = dict(mean_shares=mean_shares, holding_gain=holding_gain,
                                   timing_gain=gross_gain[symbol] - holding_gain)
    return dict(attribution=attribution, equity=equity, cash=cash, holdings=holdings, return_pct=100*(equity/capital-1),
                drawdown_pct=100*drawdown, average_exposure_pct=100*sum(exposure)/len(exposure),
                fills=fills, fees=fees, dividends=dividends, rejection_reasons=dict(rejected))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--cost-bps", type=float, default=5)
    args = parser.parse_args()
    series = {s: history(args.directory / f"marketpilot-{s}.json", s) for s in ("AAPL","MSFT","SPY")}
    for rule in ("20/50","8-month","hold"):
        print(rule, json.dumps(replay(series, args.year, rule, cost_bps=args.cost_bps), indent=2))


if __name__ == "__main__":
    main()
