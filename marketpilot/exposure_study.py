"""Match prior-year exposure with idle cash, then evaluate frozen account sizes."""
import argparse
import math
from pathlib import Path

from .desk_replay import history, replay

RULES = ("20/50", "8-month", "hold")


def compare(series, year, base_capital=100_000):
    dates = [row.bar.timestamp.date() for row in next(iter(series.values()))]
    for required in (year - 1, year):
        sessions = [day for day in dates if day.year == required]
        if len(sessions) < 240 or sessions[0].month != 1 or sessions[-1].month != 12:
            raise ValueError(f"Expected a full evaluation year for {required}")
    if len({(d.year, d.month) for d in dates if d.year < year - 1}) < 8:
        raise ValueError("Include at least eight warm-up months before calibration")
    training = {rule: replay(series, year - 1, rule, capital=base_capital) for rule in RULES}
    target = min(row["average_exposure_pct"] for row in training.values())
    if target <= 0:
        raise ValueError("Cannot match exposure when a rule stayed in cash")
    rows = []
    for rule, row in training.items():
        capital = base_capital
        for _ in range(12):
            observed = row["average_exposure_pct"]
            if math.isclose(observed, target, rel_tol=1e-6):
                break
            capital *= observed / target
            row = replay(series, year - 1, rule, capital=capital)
        else:
            raise ValueError(f"Could not match exposure for {rule}")
        test = replay(series, year, rule, capital=capital)
        rows.append((rule, capital, observed, test))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--year", type=int, default=2025)
    args = parser.parse_args()
    series = {s: history(args.directory / f"marketpilot-{s}.json", s) for s in ("AAPL", "MSFT", "SPY")}
    print("rule    starting USD    prior exposure    test exposure     return    drawdown")
    for rule, capital, exposure, test in compare(series, args.year):
        print(f"{rule:8} {capital:12,.2f} {exposure:14.4f}% {test['average_exposure_pct']:13.4f}%"
              f" {test['return_pct']:9.4f}% {test['drawdown_pct']:9.4f}%")


if __name__ == "__main__":
    main()
