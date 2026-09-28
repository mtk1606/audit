import numpy as np
import pytest
from fixtures import calibration, session

from asaudit.attribution.grid import ALL_CONFIGS, build_models
from asaudit.sim.engine import Engine, EngineConfig, ReplaySource
from asaudit.strategy.avellaneda_stoikov import ASQuoter


@pytest.mark.parametrize("g", ALL_CONFIGS, ids=lambda g: g.label)
def test_each_grid_config_completes_on_one_session(g):
    s, cal = session(20, 300.0), calibration()
    fill, info, comp = build_models(g, cal, "uniform")
    r = Engine(EngineConfig(max_inventory=20), fill, info, comp).run(
        ReplaySource(s, 100_000_000, s.start_ns, s.end_ns),
        ASQuoter(1e-4, cal.sigma, cal.intensity.k, 300.0, s.tick),
        np.random.default_rng(1),
        s.session_id,
    )
    assert r.n_steps == 3000 and r.n_fills > 0 and np.isfinite(r.pnl_path).all()


def test_a2_charge_sign_matches_embedding():
    s, cal = session(20, 300.0), calibration()
    charges = {}
    for g in ALL_CONFIGS:
        if g.a3:
            continue
        fill, info, comp = build_models(g, cal, "uniform")
        r = Engine(EngineConfig(max_inventory=20), fill, info, comp).run(
            ReplaySource(s, 100_000_000, s.start_ns, s.end_ns),
            ASQuoter(1e-4, cal.sigma, cal.intensity.k, 300.0, s.tick),
            np.random.default_rng(1),
            s.session_id,
        )
        charges[g.label] = r.charges
    assert charges["000"] == 0 and charges["110"] == 0  # nothing to add or remove
    assert charges["010"] > 0  # adverse selection added to flow-independent fills
    assert charges["100"] < 0  # observed adverse selection credited back
