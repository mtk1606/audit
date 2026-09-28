"""(A1, A2, A3) = (off, off, off) must reduce to the M1 law (PRD 5.4 / M2).

The engine runs per path, in integer quanta of 1e-4 price units, with passive
quote rounding. It is compared with the exact population moments of the M1
capped-Bernoulli law, not with another simulation. Tolerance: 4.5 standard
errors of an n-path estimate; rounding shifts quotes by at most 1e-4.
"""

import math

import numpy as np
import pytest

from asaudit.sim.competition.frozen import FrozenBook
from asaudit.sim.engine import BinaryMidSource, Engine, EngineConfig
from asaudit.sim.fills.poisson import PoissonFillModel
from asaudit.sim.flow.neutral import NeutralFlow
from asaudit.sim.moments import distribution_moments
from asaudit.sim.replication import SimulationConfig
from asaudit.strategy.avellaneda_stoikov import ASQuoter

Q = 1e4  # quanta per price unit
N_PATHS = 1500


def run_engine(gamma: float, symmetric: bool, seed: int) -> tuple[np.ndarray, np.ndarray]:
    engine = Engine(
        EngineConfig(), PoissonFillModel(140.0, 1.5 / Q, "saturate"), NeutralFlow(), FrozenBook()
    )
    quoter = ASQuoter(
        gamma / Q, 2.0 * Q, 1.5 / Q, 1.0, 1, symmetric=symmetric, average_spread=symmetric
    )
    profits, inventories = [], []
    for child in np.random.SeedSequence(seed).spawn(N_PATHS):
        mid_rng, fill_rng = (np.random.default_rng(c) for c in child.spawn(2))
        source = BinaryMidSource(100 * Q, 2.0 * Q, 5_000_000, 200, mid_rng)
        result = engine.run(source, quoter, fill_rng, "m1")
        profits.append(result.pnl / Q)
        inventories.append(result.inventory)
    return np.array(profits), np.array(inventories)


@pytest.mark.parametrize("gamma", [0.1, 1.0])
@pytest.mark.parametrize("symmetric", [False, True])
def test_off_off_off_reduces_to_m1_population_law(gamma, symmetric):
    cfg = SimulationConfig(
        gamma=gamma,
        probability="saturate",
        symmetric=symmetric,
        spread="average" if symmetric else "equation",
    )
    m = distribution_moments(cfg)
    profit, inventory = run_engine(gamma, symmetric, seed=20260928 + int(gamma * 10) + symmetric)
    sd = math.sqrt(m.profit_variance)
    assert abs(profit.mean() - m.profit_mean) < 4.5 * sd / math.sqrt(N_PATHS)
    se_sd = sd * math.sqrt((m.profit_kurtosis - 1) / (4 * N_PATHS))
    assert abs(profit.std(ddof=1) - sd) < 4.5 * se_sd
    q_sd = math.sqrt(m.inventory_variance)
    assert abs(inventory.mean()) < 4.5 * q_sd / math.sqrt(N_PATHS)
    se_q = q_sd * math.sqrt((m.inventory_kurtosis - 1) / (4 * N_PATHS))
    assert abs(inventory.std(ddof=1) - q_sd) < 4.5 * se_q
