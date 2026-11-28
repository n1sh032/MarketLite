from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from marketpilot import exposure_study as study


def test_evaluation_cannot_influence_calibration(monkeypatch):
    first = datetime(2023, 1, 1)
    dates = [first + timedelta(days=i) for i in range(365 + 366 + 365)]
    series = {"SPY": [SimpleNamespace(bar=SimpleNamespace(timestamp=d)) for d in dates]}
    observed = []
    invested = {"20/50": 500, "8-month": 750, "hold": 1000}

    def replay(series, year, rule, capital):
        exposure = invested[rule] / capital * 100
        if year == 2025:
            observed.append((rule, capital))
            exposure *= 2
        return {"average_exposure_pct": exposure}

    monkeypatch.setattr(study, "replay", replay)
    rows = study.compare(series, 2025)
    assert observed == list(zip(study.RULES, [100000, 150000, 200000]))
    for _, _, calibrated, later in rows:
        assert calibrated == pytest.approx(.5)
        assert later["average_exposure_pct"] == pytest.approx(1)
