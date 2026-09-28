import itertools
import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from asaudit.attribution.metrics import UndefinedMetric, gap_bps
from asaudit.attribution.shapley import shapley
from asaudit.data.regimes import tercile, tercile_edges
from asaudit.eval.bootstrap import politis_white_block_length, stationary_bootstrap_mean
from asaudit.eval.optimize import sep_cma_es
from asaudit.eval.walkforward import walk_forward
from asaudit.strategy.policy_class import PolicyQuoter, PolicySpace
from asaudit.types import MarketState, RegimeTag

LABELS = ["".join(b) for b in itertools.product("01", repeat=3)]


@given(st.lists(st.floats(-1e3, 1e3), min_size=8, max_size=8))
def test_shapley_efficiency(values):
    v = dict(zip(LABELS, values, strict=True))
    phi = shapley(v)
    assert sum(phi.values()) == pytest.approx(v["111"] - v["000"], abs=1e-6)


def test_shapley_additive_game_recovers_each_axis():
    w = {"A1": 3.0, "A2": -5.0, "A3": 0.25}
    v = {
        lab: sum(w[a] for a, bit in zip(("A1", "A2", "A3"), lab, strict=True) if bit == "1")
        for lab in LABELS
    }
    assert shapley(v) == pytest.approx(w)


def test_shapley_splits_pure_interaction_equally():
    v = dict.fromkeys(LABELS, 0.0)
    v["110"] = v["111"] = 6.0  # A1 and A2 matter only jointly
    phi = shapley(v)
    assert phi["A1"] == pytest.approx(3.0) and phi["A2"] == pytest.approx(3.0)
    assert phi["A3"] == pytest.approx(0.0)


def test_shapley_requires_complete_grid():
    with pytest.raises(ValueError):
        shapley({"000": 0.0})


def test_gap_bps_definition_and_undefined_cases():
    assert gap_bps(150.0, 100.0, 10_000.0) == pytest.approx(50.0)
    with pytest.raises(UndefinedMetric):
        gap_bps(1.0, 0.0, 0.0)
    with pytest.raises(UndefinedMetric):
        gap_bps(math.nan, 0.0, 1.0)


def test_block_length_grows_with_persistence():
    rng = np.random.default_rng(0)
    iid = rng.standard_normal(400)
    ar = np.zeros(400)
    for t in range(1, 400):
        ar[t] = 0.85 * ar[t - 1] + rng.standard_normal()
    assert politis_white_block_length(iid) < 2.5
    assert politis_white_block_length(ar) > 4


def test_stationary_bootstrap_covers_true_mean():
    rng = np.random.default_rng(1)
    hits = 0
    for _ in range(200):
        x = rng.standard_normal(40) + 2.0
        ci = stationary_bootstrap_mean(x, rng, repeats=300)
        hits += ci.low <= 2.0 <= ci.high
    assert 0.88 <= hits / 200 <= 0.99  # nominal 95%, percentile CI slightly liberal at n=40


def test_bootstrap_rejects_nonfinite():
    with pytest.raises(ValueError):
        stationary_bootstrap_mean(np.array([1.0, math.nan]), np.random.default_rng(0))


def test_sep_cma_es_finds_quadratic_maximum():
    target = np.array([1.0, -2.0, 0.5, 3.0])
    r = sep_cma_es(
        lambda x: -float(((x - target) ** 2).sum()),
        np.zeros(4),
        1.0,
        2000,
        np.random.default_rng(0),
    )
    assert np.allclose(r.x, target, atol=1e-2) and r.converged


def test_sep_cma_es_reports_non_convergence_under_tiny_budget():
    r = sep_cma_es(
        lambda x: -float((x**2).sum()) + 100 * x[0],
        np.zeros(6),
        0.1,
        30,
        np.random.default_rng(0),
        patience=1,
        rel_tol=1e-9,
    )
    assert not r.converged


def test_walk_forward_never_trains_on_test_episode():
    seen: list[tuple[int, ...]] = []

    class Result:
        def __init__(self, n):
            self.x, self.value, self.converged, self.evaluations = np.zeros(1), float(n), True, 1

    def fit(train, warm):
        seen.append(tuple(train))
        return Result(len(train))

    folds = walk_forward(list(range(6)), 2, fit, lambda ep, theta: float(ep))
    assert [f.test_index for f in folds] == [2, 3, 4, 5]
    assert all(max(train) < f.test_index for train, f in zip(seen, folds, strict=True))


def state(q: int, imb: float) -> MarketState:
    return MarketState(0, 1_000_050.0, None, 50.0, imb, 0.5, q, 0.0, RegimeTag())


def test_linear_skew_policy_skews_with_inventory_and_clips():
    space = PolicySpace("linear_skew", delta_max=4.0)
    theta = np.array([1.0, 0.5, 0, 0, 0, 1.0, -0.5, 0, 0, 0])
    quoter = PolicyQuoter(space, theta, 100, 50.0)
    db, da = quoter.distances(state(2, 0.0))
    assert (db, da) == (2.0, 0.0)  # long inventory: bid further away, ask at the mid
    assert quoter.distances(state(20, 0.0))[0] == 4.0  # clipped
    q = quoter.on_market_update(state(2, 0.0))
    assert q.bid_px_ticks % 100 == 0 and q.ask_px_ticks % 100 == 0
    assert q.bid_px_ticks <= 1_000_050 - 200 and q.ask_px_ticks >= 1_000_050


def test_tabular_policy_indexes_its_table():
    space = PolicySpace("tabular_binned")
    theta = np.arange(space.dim, dtype=np.float64) % 7 * 0.5
    quoter = PolicyQuoter(space, theta, 100, 50.0)
    assert all(0 <= d <= space.delta_max for d in quoter.distances(state(-19, -0.99)))
    with pytest.raises(ValueError):
        PolicyQuoter(space, np.zeros(3), 100, 50.0)


@settings(max_examples=50)
@given(st.lists(st.floats(0, 100), min_size=3, max_size=60), st.floats(0, 100))
def test_terciles_partition(values, x):
    edges = tercile_edges(values)
    assert edges[0] <= edges[1] and tercile(x, edges) in (0, 1, 2)
