import itertools
import math

import numpy as np
import pytest

from asaudit.eval.replication import Targets
from asaudit.eval.sensitivity import metric_tests, ratio_test
from asaudit.sim.moments import DistributionMoments, distribution_moments, exact_moments
from asaudit.sim.replication import SimulationConfig, simulate


def side_probability(distance, cfg):
    raw = cfg.A * math.exp(-cfg.k * distance) * cfg.dt
    return -math.expm1(-raw) if cfg.probability == "poisson" else min(raw, 1)


def enumerate_paths(cfg, steps):
    """Independent brute force over every (bid, ask, mid) outcome sequence."""
    outcomes = []
    for path in itertools.product(itertools.product((0, 1), (0, 1), (-1, 1)), repeat=steps):
        probability, cash, q, mid = 1.0, 0.0, cfg.q0, cfg.s0
        for step, (buy, sell, direction) in enumerate(path):
            risk = cfg.gamma * cfg.sigma**2 * (cfg.horizon - step * cfg.dt)
            width = 2 * math.log1p(cfg.gamma / cfg.k) / cfg.gamma + risk
            center = mid - q * risk
            bid, ask = center - width / 2, center + width / 2
            pb, pa = side_probability(mid - bid, cfg), side_probability(ask - mid, cfg)
            probability *= (pb if buy else 1 - pb) * (pa if sell else 1 - pa) / 2
            cash += sell * ask - buy * bid
            q += buy - sell
            mid += direction * cfg.sigma * math.sqrt(cfg.dt)
        outcomes.append((probability, cash + q * mid - cfg.q0 * cfg.s0, q))
    p, x, q = np.array(outcomes).T
    assert p.sum() == pytest.approx(1)
    mx, mq = p @ x, p @ q
    return mx, p @ (x - mx) ** 2, p @ (x - mx) ** 4, mq, p @ (q - mq) ** 2, p @ (q - mq) ** 4


@pytest.mark.parametrize("rule", ["saturate", "poisson"])
@pytest.mark.parametrize("q0,A", [(0, 1), (2, 3), (-1, 20)])
def test_fourth_moments_match_exhaustive_paths(rule, q0, A):
    cfg = SimulationConfig(dt=1 / 3, gamma=0.1, q0=q0, A=A, probability=rule)
    m = distribution_moments(cfg)
    expected = enumerate_paths(cfg, 3)
    actual = (
        m.profit_mean,
        m.profit_variance,
        m.profit_mu4,
        m.inventory_mean,
        m.inventory_variance,
        m.inventory_mu4,
    )
    np.testing.assert_allclose(actual, expected, rtol=1e-9, atol=1e-10)


def test_shift_does_not_change_central_moments():
    cfg = SimulationConfig(gamma=0.1, probability="saturate", dt=0.02)
    a, b = distribution_moments(cfg), distribution_moments(cfg, shift=60.0)
    assert a.profit_mean == pytest.approx(b.profit_mean, rel=1e-12)
    assert a.profit_variance == pytest.approx(b.profit_variance, rel=1e-8)
    assert a.profit_mu4 == pytest.approx(b.profit_mu4, rel=1e-6)


@pytest.mark.parametrize("rule", ["saturate", "poisson"])
def test_two_independent_recurrences_agree(rule):
    cfg = SimulationConfig(gamma=1.0, probability=rule)
    a, b = exact_moments(cfg), distribution_moments(cfg, shift=31.0)
    assert b.profit_mean == pytest.approx(a.profit_mean, rel=1e-12)
    assert b.profit_variance == pytest.approx(a.profit_variance, rel=1e-9)
    assert b.inventory_variance == pytest.approx(a.inventory_variance, rel=1e-12)


def test_poisson_rule_is_valid_where_strict_is_not():
    with pytest.raises(ValueError, match="probability"):
        exact_moments(SimulationConfig(gamma=1.0, probability="strict"))
    m = distribution_moments(SimulationConfig(gamma=1.0, probability="poisson"))
    assert m.expected_probability_exceedances > 0  # counted, but not invalid


def test_monte_carlo_agrees_with_poisson_population_law():
    cfg = SimulationConfig(gamma=1.0, probability="poisson", n_paths=20000)
    result = simulate(cfg, np.random.SeedSequence(7))
    m = distribution_moments(cfg, shift=31.0)
    se = math.sqrt(m.profit_variance / cfg.n_paths)
    assert abs(result.profit.mean() - m.profit_mean) < 4 * se
    se_sd = math.sqrt(m.profit_variance * (m.profit_kurtosis - 1) / (4 * cfg.n_paths))
    assert abs(result.profit.std(ddof=1) - math.sqrt(m.profit_variance)) < 4 * se_sd


def gaussian_moments(mean, sd):
    return DistributionMoments(mean, sd**2, 3 * sd**4, 0.0, 4.0, 48.0, 0.0)


def test_z_is_zero_at_population_and_uses_paper_n():
    m = gaussian_moments(65.0, 6.0)
    target = Targets(spread=1, profit_mean=65.0, profit_std=6.0, final_q_mean=0.0, final_q_std=2.0)
    tests = metric_tests(m, target, 1000)
    assert all(t["z"] == pytest.approx(0) for t in tests.values())
    # Gaussian SD standard error sd/sqrt(2n), plus rounding to 0.1.
    assert tests["profit_std"]["se"] == pytest.approx(math.sqrt(36 / 2000 + 0.01 / 12))
    assert tests["profit_mean"]["se"] == pytest.approx(math.sqrt(36 / 1000 + 0.01 / 12))


def test_z_sign_and_ratio_direction():
    inv, sym = gaussian_moments(65.0, 6.0), gaussian_moments(68.0, 12.0)
    ti = Targets(spread=1, profit_mean=66.0, profit_std=6.0, final_q_mean=0.0, final_q_std=2.0)
    ts = Targets(spread=1, profit_mean=68.0, profit_std=12.0, final_q_mean=0.0, final_q_std=2.0)
    assert metric_tests(inv, ti, 1000)["profit_mean"]["z"] > 0
    ratio = ratio_test(inv, sym, ti, ts, 1000)
    assert ratio["population"] == pytest.approx(4.0)
    assert ratio["z"] == pytest.approx(0)
