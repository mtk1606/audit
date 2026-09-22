import math

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from asaudit.sim.replication import SimulationConfig, advance, assess, bootstrap, simulate
from asaudit.strategy.avellaneda_stoikov import ASParameters, quote


@given(st.integers(-100, 100), st.floats(0, 1, allow_nan=False))
def test_inventory_sign_and_symmetry(q, t):
    p = ASParameters(gamma=0.1, sigma=2, k=1.5)
    a = quote(100, q, t, p)
    b = quote(100, q + 1, t, p)
    assert b.reservation <= a.reservation
    assert a.ask > a.bid
    assert a.ask - a.reservation == pytest.approx(a.reservation - a.bid)
    assert quote(100, -q, t, p).reservation == pytest.approx(200 - a.reservation)


def test_formula_limits_and_benchmark():
    p = ASParameters(gamma=0.1, sigma=2, k=1.5)
    assert quote(100, 0, 0, p).reservation == 100
    assert quote(100, 9, 1, p).reservation == 100
    assert quote(100, 5, 0, p, symmetric=True).reservation == 100
    assert quote(100, 0, 0, p).spread == pytest.approx(0.4 + 20 * math.log1p(0.1 / 1.5))
    assert quote(100, 0, 0, ASParameters(gamma=0, sigma=2, k=1.5)).spread == 2 / 1.5
    assert quote(100, 0, 0, ASParameters(gamma=1e-12, sigma=2, k=1.5)).spread == pytest.approx(
        2 / 1.5
    )
    assert (
        quote(100, 0, 0, ASParameters(gamma=0.1, sigma=3, k=1.5)).spread
        > quote(100, 0, 0, p).spread
    )
    assert quote(100, 0, 0, p).spread > quote(100, 0, 0.5, p).spread


@pytest.mark.parametrize("kwargs", [{"gamma": -1}, {"sigma": float("nan")}, {"k": 0}])
def test_bad_parameters(kwargs):
    with pytest.raises(ValueError):
        ASParameters(**kwargs)


def test_accounting_fill_at_old_quote_then_mark_at_new_mid():
    cash, q, pnl = advance(
        np.array([0.0]),
        np.array([0]),
        np.array([99.0]),
        np.array([101.0]),
        np.array([True]),
        np.array([False]),
        np.array([102.0]),
    )
    assert cash[0] == -99
    assert q[0] == 1
    assert pnl[0] == 3
    cash, q, pnl = advance(
        cash,
        q,
        np.array([99.0]),
        np.array([101.0]),
        np.array([True]),
        np.array([True]),
        np.array([98.0]),
    )
    assert cash[0] == -97
    assert q[0] == 1
    assert pnl[0] == 1


def test_determinism_binary_mid_and_independent_streams():
    c = SimulationConfig(n_paths=50, A=0, gamma=0.1)
    a = simulate(c, np.random.SeedSequence(12))
    b = simulate(c, np.random.SeedSequence(12))
    assert a.profit.tobytes() == b.profit.tobytes()
    assert a.mid.tobytes() == b.mid.tobytes()
    assert not a.profit.any()
    lattice = (a.mid - c.s0) / (c.sigma * math.sqrt(c.dt))
    np.testing.assert_allclose(lattice, np.round(lattice), atol=1e-10)
    children = np.random.SeedSequence(12).spawn(2)
    assert not np.array_equal(simulate(c, children[0]).mid, simulate(c, children[1]).mid)


def test_invalid_probability_rejected_not_silently_clipped():
    c = SimulationConfig(A=10000, n_paths=10)
    with pytest.raises(ValueError, match="probability"):
        simulate(c, np.random.SeedSequence(1))
    result = simulate(
        SimulationConfig(A=10000, n_paths=10, probability="saturate"), np.random.SeedSequence(1)
    )
    assert result.probability_exceedances > 0


def test_invalid_grid():
    with pytest.raises(ValueError):
        SimulationConfig(dt=0.003)


def test_bootstrap_and_acceptance_do_not_hide_mismatch():
    rng = np.random.default_rng(10)
    metrics = bootstrap(np.arange(100, dtype=float), np.arange(100), rng, 200)
    assert metrics["profit_mean"]["low"] < 49.5 < metrics["profit_mean"]["high"]
    assert assess(metrics, {"profit_mean": -100})["profit_mean"] is False
    assert assess(metrics, {"profit_mean": 49.5})["profit_mean"] is True
