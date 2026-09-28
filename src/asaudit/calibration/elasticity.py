"""Join and cancel intensity at the touch as functions of depth (PRD 4.2).

Per interval and side, count joins (ADD) and cancellations (CANCEL/DELETE) at
the touch price that was best at the interval start, then fit Poisson GLMs:
log E[count] = b0 + e * log(depth) + b_imb * imbalance + b_spread * wide + b_vol * vol_z.
``e`` is the depth elasticity used by ElasticityCompetition. queue_age is not
used: aggregate level data has no age for the level as a whole. Intervals must be
short: depth at the interval start is a stale regressor, and on the synthetic
fixture 1 s intervals attenuate both elasticities by about half versus 50 ms.
"""

from dataclasses import dataclass

import numpy as np

from asaudit.calibration.glm import CalibrationError, GLMFit, fit_glm
from asaudit.sim.session import ReplaySession
from asaudit.types import EventType

_CANCELS = (int(EventType.CANCEL), int(EventType.DELETE))


@dataclass(frozen=True, slots=True)
class ElasticityFit:
    join_elasticity: float
    join_se: float
    cancel_elasticity: float
    cancel_se: float
    join: GLMFit
    cancel: GLMFit
    n_intervals: int


def fit_elasticity(session: ReplaySession, interval_ns: int = 50_000_000) -> ElasticityFit:
    s = session
    rows: list[tuple[float, float, float, float, float, float]] = []
    mids: list[float] = []
    t = s.start_ns
    while t + interval_ns <= s.end_ns:
        lo, hi = s.rows_before(t), s.rows_before(t + interval_ns)
        mids.append(s.mid(lo))
        for side, px, sz in ((1, s.bid_px, s.bid_sz), (-1, s.ask_px, s.ask_sz)):
            if sz[lo, 0] <= 0:
                continue
            price, depth = int(px[lo, 0]), int(sz[lo, 0])
            sel = slice(lo, hi)
            at = (s.side[sel] == side) & (s.price[sel] == price)
            joins = int((at & (s.event_type[sel] == int(EventType.ADD))).sum())
            cancels = int((at & np.isin(s.event_type[sel], _CANCELS)).sum())
            b, a = int(s.bid_sz[lo, 0]), int(s.ask_sz[lo, 0])
            imb = side * (b - a) / (b + a) if b + a else 0.0
            wide = float((int(s.ask_px[lo, 0]) - int(s.bid_px[lo, 0])) > s.tick)
            rows.append((joins, cancels, np.log(depth), imb, wide, len(mids) - 1))
        t += interval_ns
    if len(rows) < 20:
        raise CalibrationError("too few intervals for elasticity fit")
    arr = np.asarray(rows, dtype=np.float64)
    moves = np.abs(np.diff(np.asarray(mids)))
    vol = np.concatenate([[moves[:10].mean() if len(moves) else 0.0], moves])
    v = vol[arr[:, 5].astype(int)]
    vol_z = (v - v.mean()) / (v.std() or 1.0)
    X = np.column_stack([np.ones(len(arr)), arr[:, 2], arr[:, 3], arr[:, 4], vol_z])
    if arr[:, 4].std() == 0:
        X = np.delete(X, 3, axis=1)  # no wide-spread intervals: drop the unidentified column
    join = fit_glm(X, arr[:, 0], "poisson")
    cancel = fit_glm(X, arr[:, 1], "poisson")
    return ElasticityFit(
        float(join.coef[1]),
        float(join.se[1]),
        float(cancel.coef[1]),
        float(cancel.se[1]),
        join,
        cancel,
        len(arr),
    )
