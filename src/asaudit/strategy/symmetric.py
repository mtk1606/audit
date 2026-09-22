"""Inventory-independent benchmark using the same time-dependent spread."""

from asaudit.strategy.avellaneda_stoikov import (
    AnalyticalQuote,
    ASParameters,
    liquidity_spread,
    quote,
)


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
