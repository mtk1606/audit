"""Primary metric (PRD M3): gap_bps = (PnL_pco - PnL_strategy) / notional * 1e4."""

import math


class UndefinedMetric(ValueError):
    pass


def gap_bps(pnl_pco: float, pnl_strategy: float, notional_strategy: float) -> float:
    """Notional is the strategy's traded notional, in the same quanta as P&L."""
    if not (math.isfinite(pnl_pco) and math.isfinite(pnl_strategy)):
        raise UndefinedMetric("non-finite P&L")
    if notional_strategy <= 0:
        raise UndefinedMetric("strategy traded no notional; gap_bps undefined")
    return (pnl_pco - pnl_strategy) / notional_strategy * 1e4


def pnl_bps(pnl: float, notional: float) -> float:
    if notional <= 0:
        raise UndefinedMetric("no notional traded")
    return pnl / notional * 1e4
