"""Cash, inventory and P&L with an independent decomposition check every step."""

import math
from dataclasses import dataclass, field

from asaudit.types import Fill


@dataclass(slots=True)
class Ledger:
    cash: float = 0.0
    inventory: int = 0
    charges: float = 0.0
    notional: float = 0.0
    n_fills: int = 0
    spread_capture: float = 0.0
    inventory_pnl: float = 0.0
    max_identity_error: float = 0.0
    _mark: float = field(default=math.nan)

    def start(self, mid: float) -> None:
        self._mark = mid

    def apply_fill(self, f: Fill, charge: float) -> None:
        side = int(f.side)
        # Revalue open inventory to the fill's mid before it changes.
        self.inventory_pnl += self.inventory * (f.mid_at_fill - self._mark)
        self._mark = f.mid_at_fill
        self.cash -= side * f.price_ticks * f.size
        self.inventory += side * f.size
        self.spread_capture += side * (f.mid_at_fill - f.price_ticks) * f.size
        self.charges += charge
        self.notional += f.price_ticks * f.size
        self.n_fills += 1

    def mark(self, mid: float, tolerance: float) -> float:
        """P&L at ``mid``; asserts cash + q*mid - charges equals the decomposition."""
        self.inventory_pnl += self.inventory * (mid - self._mark)
        self._mark = mid
        pnl = self.cash + self.inventory * mid - self.charges
        decomposed = self.spread_capture + self.inventory_pnl - self.charges
        error = abs(pnl - decomposed)
        self.max_identity_error = max(self.max_identity_error, error)
        if not math.isfinite(pnl) or error > tolerance * max(1.0, abs(self.notional)):
            raise ArithmeticError(f"accounting identity failed: {pnl} != {decomposed}")
        return pnl
