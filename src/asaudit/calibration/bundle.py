"""All calibrated inputs for one ablation run, fitted on calibration data only."""

from dataclasses import dataclass

import numpy as np

from asaudit.calibration.adverse import MarkoutTable, executions
from asaudit.calibration.elasticity import ElasticityFit, fit_elasticity
from asaudit.calibration.intensity import IntensityFit, fit_intensity
from asaudit.calibration.queue_fill import QueueFillFit, fit_queue_fill
from asaudit.sim.session import ReplaySession


@dataclass(frozen=True, slots=True)
class Calibration:
    intensity: IntensityFit
    markout: MarkoutTable
    elasticity: ElasticityFit
    queue_fill: QueueFillFit
    sigma: float  # quanta per sqrt(second), realized on the calibration sessions
    session_ids: tuple[str, ...]


def realized_sigma(session: ReplaySession, sample_ns: int = 1_000_000_000) -> float:
    grid = np.arange(session.start_ns, session.end_ns, sample_ns)
    mids = np.array([session.mid(session.rows_before(int(t))) for t in grid])
    return float(np.std(np.diff(mids), ddof=1) / np.sqrt(sample_ns / 1e9))


def calibrate(
    sessions: list[ReplaySession], rng: np.random.Generator, markout_horizon_ns: int
) -> Calibration:
    """Pooling rule: intensity/elasticity/queue fits on the longest calibration
    session; the markout table pools executions across all of them."""
    if not sessions:
        raise ValueError("calibration requires at least one session")
    main = max(sessions, key=lambda s: s.end_ns - s.start_ns)
    samples = [executions(s, markout_horizon_ns) for s in sessions]
    pooled = type(samples[0])(
        *(np.concatenate([getattr(x, f) for x in samples]) for f in samples[0].__slots__)
    )
    return Calibration(
        fit_intensity(main),
        MarkoutTable(pooled),
        fit_elasticity(main),
        fit_queue_fill(main, rng),
        float(np.mean([realized_sigma(s) for s in sessions])),
        tuple(s.session_id for s in sessions),
    )
