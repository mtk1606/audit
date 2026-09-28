"""Inventory-independent benchmark using the same time-dependent spread."""

import math

from asaudit.strategy.avellaneda_stoikov import (
    AnalyticalQuote,
    ASParameters,
    liquidity_spread,
    quote,
)
from asaudit.types import EpisodeContext, Fill, MarketState, Quote


def symmetric_quote(mid: float, t: float, params: ASParameters) -> AnalyticalQuote:
    return quote(mid, 0, t, params, symmetric=True)


def average_spread_quote(mid: float, params: ASParameters) -> AnalyticalQuote:
    """Published section 3.3 benchmark: continuous time-average over [0,T]."""
    # Reuse quote input validation before constructing the average benchmark.
    quote(mid, 0, 0, params)
    spread = (
        liquidity_spread(params.gamma, params.k)
        + params.gamma * params.sigma**2 * params.horizon / 2
    )
    return AnalyticalQuote(mid - spread / 2, mid + spread / 2, mid, spread)


class SymmetricQuoter:
    """Constant half-spread around the mid, in venue ticks (PRD M3 benchmark)."""

    def __init__(self, half_spread_ticks: float, tick: int, name: str = "symmetric") -> None:
        if half_spread_ticks < 0:
            raise ValueError("half spread must be nonnegative")
        self.half, self.tick, self.name = half_spread_ticks, tick, name

    def reset(self, ctx: EpisodeContext) -> None:
        return None

    def on_market_update(self, s: MarketState) -> Quote:
        bid = math.floor((s.mid - self.half * self.tick) / self.tick) * self.tick
        ask = math.ceil((s.mid + self.half * self.tick) / self.tick) * self.tick
        return Quote(s.ts_ns, int(bid), 1, int(ask), 1)

    def on_fill(self, f: Fill, s: MarketState) -> None:
        return None
