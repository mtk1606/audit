"""Markout curves and the conditional adverse-move table used by A2.

For each visible execution the passive side s is known. Markout at horizon h is
s * (mid(t + h) - price); the adverse move is -s * (mid(t + h) - mid(t)),
positive when the price moves against the passive order. Queue position at
entry is reconstructed from order ids for orders added during the session;
orders resting at the session start have unknown entry and are excluded from
queue-conditioned cells only.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from asaudit.calibration.glm import CalibrationError
from asaudit.sim.flow.base import FillFeatures
from asaudit.sim.session import ReplaySession
from asaudit.types import EventType, Fill

IMBALANCE_EDGES = (-1 / 3, 1 / 3)


@dataclass(frozen=True, slots=True)
class ExecutionSample:
    ts_ns: NDArray[np.int64]
    side: NDArray[np.int64]
    adverse: NDArray[np.float64]  # at the calibration horizon
    markout: NDArray[np.float64]
    queue_entry: NDArray[np.int64]  # -1 when unknown
    spread_ticks: NDArray[np.int64]
    imbalance: NDArray[np.float64]  # signed toward the passive side


def executions(session: ReplaySession, horizon_ns: int) -> ExecutionSample:
    s = session
    entry: dict[int, int] = {}
    rows: list[tuple[int, int, float, float, int, int, float]] = []
    for i in range(s.n_events):
        etype, side, price = int(s.event_type[i]), int(s.side[i]), int(s.price[i])
        if etype == int(EventType.ADD):
            entry[int(s.order_id[i])] = s.level_depth(i, side, price)
        elif etype == int(EventType.EXECUTE):
            t = int(s.ts_ns[i])
            if t + horizon_ns > s.end_ns:
                continue
            later = s.rows_before(t + horizon_ns)
            mid0, mid1 = s.mid(i), s.mid(later)
            b, a = int(s.bid_sz[i, 0]), int(s.ask_sz[i, 0])
            spread = (int(s.ask_px[i, 0]) - int(s.bid_px[i, 0])) // s.tick
            imb = side * (b - a) / (b + a) if b + a else 0.0
            rows.append(
                (
                    t,
                    side,
                    -side * (mid1 - mid0),
                    side * (mid1 - price),
                    entry.get(int(s.order_id[i]), -1),
                    spread,
                    imb,
                )
            )
    if not rows:
        raise CalibrationError("no executions with a complete markout horizon")
    cols = list(zip(*rows, strict=True))
    return ExecutionSample(
        np.asarray(cols[0], dtype=np.int64),
        np.asarray(cols[1], dtype=np.int64),
        np.asarray(cols[2], dtype=np.float64),
        np.asarray(cols[3], dtype=np.float64),
        np.asarray(cols[4], dtype=np.int64),
        np.asarray(cols[5], dtype=np.int64),
        np.asarray(cols[6], dtype=np.float64),
    )


def markout_curves(
    session: ReplaySession, horizons_ns: tuple[int, ...]
) -> dict[int, dict[str, float]]:
    out: dict[int, dict[str, float]] = {}
    for h in horizons_ns:
        e = executions(session, h)
        n = len(e.markout)
        out[h] = {
            "n": float(n),
            "markout_mean": float(e.markout.mean()),
            "adverse_mean": float(e.adverse.mean()),
            "adverse_se": float(e.adverse.std(ddof=1) / np.sqrt(n)) if n > 1 else float("nan"),
        }
    return out


def _imb_bucket(x: float) -> int:
    return int(np.searchsorted(IMBALANCE_EDGES, x))


class MarkoutTable:
    """Shrunk cell means of the adverse move over (queue, spread, imbalance).

    Queue buckets use sample quantile edges. Cells shrink toward the
    queue-marginal (spread, imbalance) mean with prior weight ``n0``; Poisson
    (non-queue) fills use the queue-marginal cells, since AS has no queue.
    """

    def __init__(self, sample: ExecutionSample, n_queue_buckets: int = 3, n0: float = 20.0) -> None:
        known = sample.queue_entry >= 0
        if known.sum() < n_queue_buckets:
            raise CalibrationError("too few executions with known queue entry")
        q = sample.queue_entry[known]
        self.queue_edges = tuple(
            float(v) for v in np.quantile(q, np.linspace(0, 1, n_queue_buckets + 1)[1:-1])
        )
        self.overall = float(sample.adverse.mean())
        self.marginal: dict[tuple[int, int], float] = {}
        self.cells: dict[tuple[int, int, int], float] = {}
        self.counts: dict[tuple[int, int, int], int] = {}
        sp = np.minimum(sample.spread_ticks, 2)
        ib = np.array([_imb_bucket(x) for x in sample.imbalance])
        for key2 in {(int(a), int(b)) for a, b in zip(sp, ib, strict=True)}:
            mask = (sp == key2[0]) & (ib == key2[1])
            m = int(mask.sum())
            self.marginal[key2] = (sample.adverse[mask].sum() + n0 * self.overall) / (m + n0)
        qb = np.searchsorted(self.queue_edges, sample.queue_entry, side="right")
        for key in {
            (int(a), int(b), int(c))
            for a, b, c in zip(qb[known], sp[known], ib[known], strict=True)
        }:
            mask = known & (qb == key[0]) & (sp == key[1]) & (ib == key[2])
            m = int(mask.sum())
            prior = self.marginal[(key[1], key[2])]
            self.cells[key] = (sample.adverse[mask].sum() + n0 * prior) / (m + n0)
            self.counts[key] = m

    def beta(self, f: Fill, features: FillFeatures) -> float:
        key2 = (min(features.spread_ticks, 2), _imb_bucket(features.imbalance))
        prior = self.marginal.get(key2, self.overall)
        if not f.is_bounded_estimate:
            return prior
        qb = int(np.searchsorted(self.queue_edges, f.queue_pos_at_entry, side="right"))
        return self.cells.get((qb, *key2), prior)
