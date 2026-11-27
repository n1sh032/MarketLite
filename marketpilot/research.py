"""Offline comparison of daily crossovers and month-end trend signals."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from statistics import mean, stdev

from .strategy import Bar, moving_average_signal


def load_prices(path, symbol):
    chart = json.loads(path.read_bytes())["chart"]["result"][0]
    if chart["meta"]["symbol"] != symbol:
        raise ValueError(f"Wrong symbol in {path}")
    prices = chart["indicators"]["adjclose"][0]["adjclose"]
    bars = []
    for stamp, close in zip(chart["timestamp"], prices, strict=True):
        if close is None or not math.isfinite(close) or close <= 0:
            raise ValueError(f"Missing adjusted close for {symbol} at {stamp}")
        bars.append(Bar(symbol, datetime.fromtimestamp(stamp, timezone.utc), close))
    if any(a.timestamp >= b.timestamp for a, b in zip(bars, bars[1:])):
        raise ValueError("Expected strictly increasing dates")
    return bars


def targets(bars, rule, start):
    # Each evaluation starts in cash. A month is complete when the next
    # session arrives. Its signal can execute at that new session's close.
    history = []
    position = 0
    for i, bar in enumerate(bars):
        previous = bars[i-1] if i else None
        new_month = previous and previous.timestamp.month != bar.timestamp.month
        if new_month:
            history.append(previous.close)
        if bar.timestamp.year >= start:
            if rule == "hold":
                position = 1
            elif rule == "20/50" and i and previous.timestamp.year >= start:
                signal = moving_average_signal(bars[max(0, i-51):i])
                if signal.action != "hold":
                    position = int(signal.action == "buy")
            elif isinstance(rule, int) and new_month and len(history) >= rule:
                position = int(history[-1] > mean(history[-rule:]))
        yield position


def evaluate(bars, rule, start, end, cost_bps):
    equity = peak = 1.0
    drawdown = 0.0
    position = trades = 0
    returns = []
    for i, target in enumerate(targets(bars, rule, start)):
        year = bars[i].timestamp.year
        if year > end:
            break
        if year < start:
            continue
        change = abs(target-position)
        gross = 1 + position * (bars[i].close / bars[i-1].close - 1) if i else 1
        factor = gross * (1 - change * cost_bps / 10000)
        equity *= factor
        peak = max(peak, equity)
        drawdown = min(drawdown, equity/peak - 1)
        trades += change
        returns.append(factor - 1)
        position = target
    if len(returns) < 2:
        raise ValueError("Insufficient evaluation history")
    vol = stdev(returns)
    return (equity ** (252/len(returns)) - 1, drawdown,
            math.sqrt(252)*mean(returns)/vol if vol else 0, trades)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Directory with marketpilot-SYMBOL.json Yahoo chart files")
    args = parser.parse_args()
    prices = {s: load_prices(args.directory / f"marketpilot-{s}.json", s) for s in ("AAPL","MSFT","SPY")}
    days = [{b.timestamp.date() for b in bars} for bars in prices.values()]
    if not all(d == days[0] for d in days) or min(days[0]).year != 2010 or max(days[0]).year != 2024:
        raise ValueError("Expected aligned 2010-2024 sessions for all three symbols")
    scores = {n: mean(evaluate(b, n, 2011, 2018, 5)[2] for b in prices.values()) for n in (8,10,12)}
    winner = max(scores, key=scores.get)
    print("Training mean Sharpe:", scores, "Selected months:", winner)
    print("2019-2024 | cost(bps) symbol rule CAGR max_drawdown Sharpe trades")
    for cost in (5, 20):
        for symbol, bars in prices.items():
            for rule in ("20/50", winner, "hold"):
                growth, loss, sharpe, count = evaluate(bars, rule, 2019, 2024, cost)
                print(cost, symbol, rule, f"{growth:.2%} {loss:.2%} {sharpe:.2f}", count)


if __name__ == "__main__":
    main()
