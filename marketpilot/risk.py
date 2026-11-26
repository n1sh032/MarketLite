from dataclasses import dataclass
import re

_SYMBOL = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


@dataclass(frozen=True)
class RiskLimits:
    allowed_symbols: frozenset[str] = frozenset({"AAPL", "MSFT", "SPY"})
    max_quantity: int = 10
    max_notional: float = 2_000.0
    max_positions: int = 5
    max_symbol_allocation: float = 0.20
    max_daily_loss: float = 1_000.0


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reasons: tuple[str, ...]


def assess_order(*, symbol: str, side: str, quantity: int, price: float,
                 limits: RiskLimits, open_positions: int = 0,
                 current_symbol_value: float = 0.0, equity: float = 10_000.0,
                 daily_pnl: float = 0.0, stale: bool = False,
                 duplicate: bool = False, held_quantity: int = 0) -> RiskDecision:
    symbol, side = symbol.strip().upper(), side.strip().lower()
    reasons: list[str] = []
    if not _SYMBOL.fullmatch(symbol): reasons.append("Invalid symbol")
    if symbol not in limits.allowed_symbols: reasons.append("Symbol is not allow-listed")
    if side not in {"buy", "sell"}: reasons.append("Side must be buy or sell")
    if isinstance(quantity, bool) or quantity <= 0: reasons.append("Quantity must be a positive integer")
    if quantity > limits.max_quantity: reasons.append("Maximum order quantity exceeded")
    if price <= 0: reasons.append("Price must be positive")
    if quantity * price > limits.max_notional: reasons.append("Maximum order notional exceeded")
    if stale: reasons.append("Market data is stale or incomplete")
    if duplicate: reasons.append("Duplicate or conflicting order exists")
    if daily_pnl <= -limits.max_daily_loss: reasons.append("Daily loss limit reached")
    if side == "sell" and quantity > held_quantity: reasons.append("Sell quantity exceeds held shares")
    if side == "buy":
        if open_positions >= limits.max_positions and current_symbol_value <= 0:
            reasons.append("Maximum open positions reached")
        if equity <= 0 or current_symbol_value + quantity * price > equity * limits.max_symbol_allocation:
            reasons.append("Per-symbol allocation limit exceeded")
    return RiskDecision(not reasons, tuple(reasons))
