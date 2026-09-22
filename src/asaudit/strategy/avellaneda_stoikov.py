"""Continuous-price analytical AS model, separate from integer venue execution."""

import math
from dataclasses import dataclass


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
