"""P(fill within horizon | queue_ahead, depth, spread, vol, imbalance), logistic.

Virtual orders are placed at the touch on a fixed time grid and advanced with
the uniform-attribution QueueFillModel, so the label uses exactly the
simulator's fill rule. The logistic model is the interpretable headline; the
binned calibration table exposes residual structure.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from asaudit.calibration.glm import GLMFit, fit_glm
from asaudit.sim.competition.frozen import FrozenBook
from asaudit.sim.fills.base import StepContext
from asaudit.sim.fills.queue import QueueFillModel
from asaudit.sim.session import ReplaySession
from asaudit.types import Side

FEATURES = ("intercept", "log1p_queue_ahead", "log1p_opposite_depth", "imbalance", "wide")


@dataclass(frozen=True, slots=True)
class QueueFillFit:
    fit: GLMFit
    features: tuple[str, ...]
    horizon_ns: int
    calibration: NDArray[np.float64]  # rows: (predicted decile mean, observed rate, n)

    def probability(
        self, queue_ahead: float, opposite_depth: float, imbalance: float, wide: float
    ) -> float:
        x = np.array([1.0, np.log1p(queue_ahead), np.log1p(opposite_depth), imbalance, wide])
        return float(1 / (1 + np.exp(-(x @ self.fit.coef))))


def fit_queue_fill(
    session: ReplaySession,
    rng: np.random.Generator,
    horizon_ns: int = 5_000_000_000,
    grid_ns: int = 1_000_000_000,
) -> QueueFillFit:
    s = session
    model = QueueFillModel("uniform")
    xs: list[list[float]] = []
    ys: list[float] = []
    t = s.start_ns
    while t + horizon_ns <= s.end_ns:
        lo, hi = s.rows_before(t), s.rows_before(t + horizon_ns)
        for side, px, sz, opp in (
            (Side.BID, s.bid_px, s.bid_sz, s.ask_sz),
            (Side.ASK, s.ask_px, s.ask_sz, s.bid_sz),
        ):
            if sz[lo, 0] <= 0 or opp[lo, 0] <= 0:
                continue
            ctx = StepContext(t, t + horizon_ns, s.mid(lo), s, lo, hi, FrozenBook())
            order = model.place(0, side, int(px[lo, 0]), 1, ctx)
            fills, _ = model.step({0: order}, ctx, rng)
            b, a = int(s.bid_sz[lo, 0]), int(s.ask_sz[lo, 0])
            wide = float((int(s.ask_px[lo, 0]) - int(s.bid_px[lo, 0])) > s.tick)
            xs.append(
                [
                    1.0,
                    np.log1p(order.queue_ahead),
                    np.log1p(int(opp[lo, 0])),
                    int(side) * (b - a) / (b + a),
                    wide,
                ]
            )
            ys.append(float(bool(fills)))
        t += grid_ns
    X, y = np.asarray(xs), np.asarray(ys)
    features: tuple[str, ...] = FEATURES
    if X[:, 4].std() == 0:
        X, features = X[:, :4], FEATURES[:4]
    fit = fit_glm(X, y, "logistic", ridge=1e-6)
    p = 1 / (1 + np.exp(-(X @ fit.coef)))
    edges = np.quantile(p, np.linspace(0, 1, 11))
    bins = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, 9)
    table = np.array(
        [
            [p[bins == b].mean(), y[bins == b].mean(), (bins == b).sum()]
            for b in range(10)
            if (bins == b).any()
        ]
    )
    return QueueFillFit(fit, features, horizon_ns, table)
