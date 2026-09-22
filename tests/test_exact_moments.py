import itertools
import math

import numpy as np
import pytest

from asaudit.sim.moments import exact_moments, symmetric_moments
from asaudit.sim.replication import SimulationConfig, simulate


def enumerate_two_steps(cfg):
    outcomes = []
    for path in itertools.product(itertools.product((0, 1), (0, 1), (-1, 1)), repeat=2):
        probability, cash, q, mid = 1.0, 0.0, cfg.q0, cfg.s0
        for step, (buy, sell, direction) in enumerate(path):
            risk = cfg.gamma * cfg.sigma**2 * (cfg.horizon - step * cfg.dt)
            width = 2 * math.log1p(cfg.gamma / cfg.k) / cfg.gamma + risk
            center = mid - q * risk
            bid, ask = center - width / 2, center + width / 2
            pb = min(cfg.A * math.exp(-cfg.k * (mid - bid)) * cfg.dt, 1)
            pa = min(cfg.A * math.exp(-cfg.k * (ask - mid)) * cfg.dt, 1)
            probability *= (pb if buy else 1 - pb) * (pa if sell else 1 - pa) / 2
            cash += sell * ask - buy * bid
            q += buy - sell
            mid += direction * cfg.sigma * math.sqrt(cfg.dt)
        outcomes.append((probability, cash + q * mid - cfg.q0 * cfg.s0, q))
    p, profit, q = np.array(outcomes).T
    return (
        float(p @ profit),
        float(p @ profit**2 - (p @ profit) ** 2),
        float(p @ q),
        float(p @ q**2 - (p @ q) ** 2),
    )


@pytest.mark.parametrize("q0,A", [(0, 1), (2, 1), (0, 20)])
def test_dynamic_program_against_exhaustive_paths(q0, A):
    cfg = SimulationConfig(dt=0.5, gamma=0.1, q0=q0, A=A, probability="saturate")
    actual = exact_moments(cfg)
    expected = enumerate_two_steps(cfg)
    np.testing.assert_allclose(
        [
            actual.profit_mean,
            actual.profit_variance,
            actual.inventory_mean,
            actual.inventory_variance,
        ],
        expected,
        atol=1e-10,
    )
    assert actual.terminal_mass == pytest.approx(1)


def test_symmetric_closed_form_matches_dynamic_program():
    cfg = SimulationConfig(symmetric=True, spread="average", q0=2, probability="saturate")
    closed = symmetric_moments(cfg)
    dp = exact_moments(cfg)
    assert dp.profit_mean == pytest.approx(closed.profit_mean)
    assert dp.profit_variance == pytest.approx(closed.profit_variance)
    assert dp.inventory_variance == pytest.approx(closed.inventory_variance)


def test_simulator_exhaustive_equal_probability_fixture(monkeypatch):
    # Every path of two bid, ask and mid trials appears once: 2**6 paths.
    bits = np.array(list(itertools.product((0, 1), repeat=6))).reshape(64, 2, 3)

    class ExhaustiveRng:
        step = 0

        def random(self, shape):
            assert shape == (64, 3)
            result = 0.25 + 0.5 * bits[:, self.step, :]
            self.step += 1
            return result

    monkeypatch.setattr(np.random, "default_rng", lambda seed: ExhaustiveRng())
    cfg = SimulationConfig(
        n_paths=64, dt=0.5, gamma=0, k=2, sigma=0.3, A=math.e, symmetric=True, spread="average"
    )
    result = simulate(cfg, np.random.SeedSequence(1))
    expected = symmetric_moments(cfg)
    assert result.profit.mean() == pytest.approx(expected.profit_mean)
    assert result.profit.var() == pytest.approx(expected.profit_variance)
    assert result.inventory.var() == pytest.approx(expected.inventory_variance)


def test_oracle_rejects_undefined_probabilities():
    with pytest.raises(ValueError, match="probability"):
        exact_moments(SimulationConfig(A=10000))
