"""Regime tagging (PRD M3): terciles of time-weighted spread, realized 1-minute
volatility and top-of-book depth, with edges computed per symbol over the full
sample. Reports use axis marginals and the spread x volatility interaction only.
"""

from dataclasses import dataclass

import numpy as np

from asaudit.sim.session import ReplaySession
from asaudit.types import RegimeTag


@dataclass(frozen=True, slots=True)
class EpisodeFeatures:
    spread_ticks: float
    volatility: float  # realized, quanta per sqrt(second), 1-minute sampling
    depth: float  # time-weighted mean of bid and ask top-level size


def episode_features(s: ReplaySession, start_ns: int, end_ns: int) -> EpisodeFeatures:
    lo, hi = s.rows_before(start_ns), s.rows_before(end_ns)
    rows = np.arange(lo, hi + 1)
    times = np.concatenate([[start_ns], s.ts_ns[lo:hi], [end_ns]]).astype(np.float64)
    weights = np.diff(times)
    spread = (s.ask_px[rows, 0] - s.bid_px[rows, 0]) / s.tick
    depth = (s.bid_sz[rows, 0] + s.ask_sz[rows, 0]) / 2
    total = weights.sum()
    minute = 60_000_000_000
    grid = np.arange(start_ns, end_ns + 1, minute)
    mids = np.array([s.mid(s.rows_before(int(t))) for t in grid])
    vol = float(np.std(np.diff(mids)) / np.sqrt(60)) if len(mids) > 2 else 0.0
    return EpisodeFeatures(float(spread @ weights / total), vol, float(depth @ weights / total))


def tercile_edges(values: list[float]) -> tuple[float, float]:
    if len(values) < 3:
        raise ValueError("tercile edges need at least three episodes")
    low, high = np.quantile(np.asarray(values), [1 / 3, 2 / 3])
    return float(low), float(high)


def tercile(value: float, edges: tuple[float, float]) -> int:
    return int(np.searchsorted(edges, value, side="right"))


def tag(
    f: EpisodeFeatures,
    spread_edges: tuple[float, float],
    vol_edges: tuple[float, float],
    depth_edges: tuple[float, float],
) -> RegimeTag:
    return RegimeTag(
        tercile(f.spread_ticks, spread_edges),
        tercile(f.volatility, vol_edges),
        tercile(f.depth, depth_edges),
    )
