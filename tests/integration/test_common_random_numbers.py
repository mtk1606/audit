"""Regression for the seeding bug: grid cells must share random streams.

Under Poisson fills A3 has no channel, so cells 000 and 001 (and 010/011) must
produce identical fills. They do only if every cell draws from the same stream
for a given (episode, strategy): common random numbers. Before the fix,
SeedSequence.spawn() advanced a counter per call and each cell got new draws.
"""

import numpy as np
from fixtures import calibration, session

from asaudit.attribution.grid import GridConfig
from asaudit.attribution.run import AblationConfig, Episode, Runner, child
from asaudit.strategy.avellaneda_stoikov import ASQuoter


def test_a1_off_cells_share_random_numbers_across_a3():
    s, cal = session(21, 120.0), calibration()
    cfg = AblationConfig.model_validate(
        {"run_name": "crn", "seed": 3, "data": {"source": "synthetic", "symbols": ["S"]}}
    )
    runner = Runner(cfg, cal, s.tick)
    e = Episode(s.symbol, 0, s, child(np.random.SeedSequence(3), 0))
    quoter = ASQuoter(1e-4, cal.sigma, cal.intensity.k, 120.0, s.tick)
    for a2 in (False, True):
        off = runner.run(e, GridConfig(False, a2, False), "uniform", quoter, 0)
        on = runner.run(e, GridConfig(False, a2, True), "uniform", quoter, 0)
        assert off.n_fills > 0
        assert off.fills == on.fills and off.pnl == on.pnl


def test_child_seeds_are_stable_under_repeated_derivation():
    root = np.random.SeedSequence(9)
    first = np.random.default_rng(child(root, 4, 1)).random(3)
    root.spawn(5)  # advancing the spawn counter must not change keyed children
    again = np.random.default_rng(child(root, 4, 1)).random(3)
    assert (first == again).all()
