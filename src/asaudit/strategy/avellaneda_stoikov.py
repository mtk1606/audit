"""Continuous-price analytical AS model, separate from integer venue execution."""

import math
from dataclasses import dataclass

from asaudit.types import EpisodeContext, Fill, MarketState, Quote


@dataclass(frozen=True, slots=True)
class ASParameters:
    gamma: float = 0.1
    sigma: float = 2.0
    k: float = 1.5
    horizon: float = 1.0

    def __post_init__(self) -> None:
        if not all(math.isfinite(v) for v in (self.gamma, self.sigma, self.k, self.horizon)):
            raise ValueError("parameters must be finite")
        if self.gamma < 0 or self.sigma < 0 or self.k <= 0 or self.horizon <= 0:
            raise ValueError("invalid risk, volatility, decay or horizon")


@dataclass(frozen=True, slots=True)
class AnalyticalQuote:
    bid: float
    ask: float
    reservation: float
    spread: float


def liquidity_spread(gamma: float, k: float) -> float:
    if gamma == 0:
        return 2 / k
    return 2 * math.log1p(gamma / k) / gamma


def quote(
    mid: float, inventory: int, t: float, params: ASParameters, *, symmetric: bool = False
) -> AnalyticalQuote:
    """Equations 3.17-3.18. Monetary values are theoretical model units."""
    if not math.isfinite(mid) or not math.isfinite(t) or not 0 <= t <= params.horizon:
        raise ValueError("invalid mid or time")
    risk = params.gamma * params.sigma**2 * (params.horizon - t)
    reservation = mid if symmetric else mid - inventory * risk
    spread = risk + liquidity_spread(params.gamma, params.k)
    return AnalyticalQuote(reservation - spread / 2, reservation + spread / 2, reservation, spread)


class ASQuoter:
    """Engine quoter. Units: prices in source quanta, time in seconds.

    ``sigma`` is quanta per sqrt(second), ``k`` per quanta, ``gamma`` per quanta.
    ``horizon_s`` is the episode length T. Continuous quotes are rounded
    passively to the venue grid: bid down, ask up.
    """

    def __init__(
        self,
        gamma: float,
        sigma: float,
        k: float,
        horizon_s: float,
        tick: int,
        *,
        symmetric: bool = False,
        average_spread: bool = False,
        name: str = "avellaneda_stoikov",
    ) -> None:
        self.params = ASParameters(gamma, sigma, k, horizon_s)
        self.tick, self.symmetric, self.average_spread = tick, symmetric, average_spread
        self.name = name

    def reset(self, ctx: EpisodeContext) -> None:
        return None

    def on_market_update(self, s: MarketState) -> Quote:
        t = self.params.horizon * (1 - s.time_remaining)
        t = min(max(t, 0.0), self.params.horizon)
        if self.average_spread:
            from asaudit.strategy.symmetric import average_spread_quote

            q = average_spread_quote(s.mid, self.params)
        else:
            q = quote(s.mid, s.inventory, t, self.params, symmetric=self.symmetric)
        bid = math.floor(q.bid / self.tick) * self.tick
        ask = math.ceil(q.ask / self.tick) * self.tick
        return Quote(s.ts_ns, int(bid), 1, int(ask), 1)

    def on_fill(self, f: Fill, s: MarketState) -> None:
        return None
