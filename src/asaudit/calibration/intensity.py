"""Fit lambda(delta) = A * exp(-k * delta) from replayed market-order reach.

A market order is a run of visible executions sharing a timestamp and passive
side. Its reach is the distance from the pre-trade mid to the deepest price it
executed at. lambda(delta_j) counts orders reaching at least delta_j per second
per side, on the grid delta_j = (j + 1/2) * tick, so j = 0 is the touch of a
one-tick market. OLS of log lambda on delta gives k and A; R-squared and the
residuals are reported because the exponential misfit is itself a finding.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from asaudit.calibration.glm import CalibrationError
from asaudit.sim.session import ReplaySession
from asaudit.types import EventType


@dataclass(frozen=True, slots=True)
class IntensityFit:
    A: float  # per second, per side
    k: float  # per price quantum
    r2: float
    distances: NDArray[np.float64]
    rates: NDArray[np.float64]
    residuals: NDArray[np.float64]
    n_market_orders: int


def market_order_reach(session: ReplaySession) -> NDArray[np.float64]:
    s = session
    reach: list[float] = []
    i, n = 0, s.n_events
    while i < n:
        if int(s.event_type[i]) != int(EventType.EXECUTE):
            i += 1
            continue
        j = i
        while (
            j + 1 < n
            and int(s.event_type[j + 1]) == int(EventType.EXECUTE)
            and s.ts_ns[j + 1] == s.ts_ns[i]
            and s.side[j + 1] == s.side[i]
        ):
            j += 1
        side = int(s.side[i])
        prices = s.price[i : j + 1]
        deepest = int(prices.min()) if side == 1 else int(prices.max())
        reach.append(side * (s.mid(i) - deepest))
        i = j + 1
    return np.asarray(reach, dtype=np.float64)


def fit_intensity(session: ReplaySession, max_levels: int = 5) -> IntensityFit:
    reach = market_order_reach(session)
    seconds = (session.end_ns - session.start_ns) / 1e9
    grid = (np.arange(max_levels) + 0.5) * session.tick
    counts = np.array([(reach >= d - 1e-9).sum() for d in grid], dtype=np.float64)
    keep = counts > 0
    if keep.sum() < 2:
        raise CalibrationError("fewer than two populated distance buckets")
    x = grid[keep].astype(np.float64)
    rates = (counts[keep] / (2 * seconds)).astype(np.float64)
    y = np.log(rates)
    slope, intercept = np.polyfit(x, y, 1)
    fitted = intercept + slope * x
    ss_res = float(((y - fitted) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 1.0
    if slope >= 0:
        raise CalibrationError("non-decreasing intensity in distance; k undefined")
    return IntensityFit(
        float(np.exp(intercept)), float(-slope), r2, x, rates, y - fitted, len(reach)
    )
