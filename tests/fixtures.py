"""Shared synthetic fixtures. Everything here is fixture data, not market data."""

from functools import cache

import numpy as np

from asaudit.calibration.bundle import Calibration, calibrate
from asaudit.sim.session import ReplaySession
from asaudit.sim.synthetic import SyntheticConfig, generate_session


@cache
def session(seed: int, duration_s: float = 120.0, **overrides: float) -> ReplaySession:
    cfg = SyntheticConfig(duration_s=duration_s, **overrides)
    return generate_session(cfg, np.random.default_rng(seed), f"syn-{seed}")


@cache
def calibration() -> Calibration:
    return calibrate([session(1000, 900.0)], np.random.default_rng(1001), 1_000_000_000)
