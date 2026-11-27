"""Values needed by the desk from a paper account snapshot."""
import math


def gross_exposure(positions):
    try:
        total = sum(abs(float(position["market_value"])) for position in positions)
    except (KeyError, ValueError, TypeError):
        return None
    return total if math.isfinite(total) else None
