"""Inventory-independent benchmark using the same time-dependent spread."""

from asaudit.strategy.avellaneda_stoikov import AnalyticalQuote, ASParameters, quote


def symmetric_quote(mid: float, t: float, params: ASParameters) -> AnalyticalQuote:
    return quote(mid, 0, t, params, symmetric=True)
