"""PolicyClassOptimum candidates (PRD 4.1): explicit, finite-dimensional classes.

Distances are in venue ticks from the mid, clipped to [delta_min, delta_max].
Features: inventory q, sigma_hat relative to the calibration sigma, top-of-book
imbalance, and depth ratio log((bid_sz + 1) / (ask_sz + 1)).
"""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from asaudit.types import EpisodeContext, Fill, MarketState, Quote

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class PolicySpace:
    klass: str
    delta_min: float = 0.0
    delta_max: float = 10.0
    max_inventory: int = 20
    q_bins: int = 9
    sigma_edges: tuple[float, ...] = (0.75, 1.33)
    imb_bins: int = 5

    @property
    def dim(self) -> int:
        if self.klass == "linear_skew":
            return 10
        if self.klass == "tabular_binned":
            return self.q_bins * (len(self.sigma_edges) + 1) * self.imb_bins * 2
        raise ValueError(f"unknown policy class {self.klass}")

    def initial(self, delta0: float) -> FloatArray:
        x = np.zeros(self.dim)
        if self.klass == "linear_skew":
            x[0] = x[5] = delta0
        else:
            x[:] = delta0
        return x


def features(s: MarketState, sigma_ref: float) -> tuple[float, float, float, float]:
    depth_ratio = 0.0
    if s.book is not None and len(s.book.bid_sz) and len(s.book.ask_sz):
        depth_ratio = math.log((int(s.book.bid_sz[0]) + 1) / (int(s.book.ask_sz[0]) + 1))
    sigma_n = s.sigma_hat / sigma_ref if sigma_ref > 0 else 1.0
    return float(s.inventory), sigma_n, s.imbalance, depth_ratio


class PolicyQuoter:
    def __init__(self, space: PolicySpace, theta: FloatArray, tick: int, sigma_ref: float) -> None:
        if len(theta) != space.dim or not np.isfinite(theta).all():
            raise ValueError("policy parameters have wrong size or are non-finite")
        self.space, self.theta, self.tick, self.sigma_ref = space, theta, tick, sigma_ref
        self.name = f"policy_class:{space.klass}"

    def reset(self, ctx: EpisodeContext) -> None:
        return None

    def distances(self, s: MarketState) -> tuple[float, float]:
        sp = self.space
        q, sig, imb, dr = features(s, self.sigma_ref)
        if sp.klass == "linear_skew":
            x = np.array([1.0, q, sig, imb, dr])
            db, da = float(self.theta[:5] @ x), float(self.theta[5:] @ x)
        else:
            edges = np.linspace(-sp.max_inventory, sp.max_inventory, sp.q_bins + 1)[1:-1]
            qi = int(np.searchsorted(edges, q, side="right"))
            si = int(np.searchsorted(sp.sigma_edges, sig, side="right"))
            ii = min(int((imb + 1) / 2 * sp.imb_bins), sp.imb_bins - 1)
            table = self.theta.reshape(sp.q_bins, len(sp.sigma_edges) + 1, sp.imb_bins, 2)
            db, da = float(table[qi, si, ii, 0]), float(table[qi, si, ii, 1])
        clip = (sp.delta_min, sp.delta_max)
        return float(np.clip(db, *clip)), float(np.clip(da, *clip))

    def on_market_update(self, s: MarketState) -> Quote:
        db, da = self.distances(s)
        bid = math.floor((s.mid - db * self.tick) / self.tick) * self.tick
        ask = math.ceil((s.mid + da * self.tick) / self.tick) * self.tick
        return Quote(s.ts_ns, int(bid), 1, int(ask), 1)

    def on_fill(self, f: Fill, s: MarketState) -> None:
        return None
