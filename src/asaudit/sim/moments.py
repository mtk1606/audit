"""Independent finite-state moment calculation for the declared discrete model.

No paths, random numbers, quote helper or simulation accounting code are reused.
All reachable inventory states are propagated; no inventory cutoff is imposed.
"""

import math
from dataclasses import dataclass

from asaudit.sim.replication import SimulationConfig


@dataclass(frozen=True, slots=True)
class ExactMoments:
    profit_mean: float
    profit_variance: float
    inventory_mean: float
    inventory_variance: float
    terminal_mass: float
    expected_probability_exceedances: float


def _probability(distance: float, cfg: SimulationConfig) -> tuple[float, bool]:
    if cfg.A == 0:
        return 0.0, False
    log_p = math.log(cfg.A) + math.log(cfg.dt) - cfg.k * distance
    if cfg.probability == "poisson":
        return -math.expm1(-math.exp(log_p)), log_p > 0
    if log_p > 0:
        if cfg.probability == "strict":
            raise ValueError("invalid probability at a reachable inventory state")
        return 1.0, True
    return math.exp(log_p), False


def exact_moments(cfg: SimulationConfig) -> ExactMoments:
    """Population moments via probability-weighted P&L moment recurrences.

    Strict reachability checks every positive-mass state, not just sampled paths.
    Exact refers to the discrete law; arithmetic uses float64 precision.
    """
    n = round(cfg.horizon / cfg.dt)
    base = 2 / cfg.k if cfg.gamma == 0 else 2 * math.log1p(cfg.gamma / cfg.k) / cfg.gamma
    # State maps q to (probability, probability-weighted profit, second moment).
    states = {cfg.q0: (1.0, 0.0, 0.0)}
    exceedances = 0.0
    for step in range(n):
        following: dict[int, tuple[float, float, float]] = {}
        risk = cfg.gamma * cfg.sigma**2 * (cfg.horizon - step * cfg.dt)
        width = base
        if cfg.spread == "equation":
            width += risk
        elif cfg.spread == "average":
            width += cfg.gamma * cfg.sigma**2 * cfg.horizon / 2
        for q, (mass, first, second) in states.items():
            shift = 0.0 if cfg.symmetric else q * risk
            bid_distance, ask_distance = width / 2 + shift, width / 2 - shift
            pb, bad_b = _probability(bid_distance, cfg)
            pa, bad_a = _probability(ask_distance, cfg)
            exceedances += mass * (int(bad_b) + int(bad_a))
            for buy, sell, weight in (
                (0, 0, (1 - pb) * (1 - pa)),
                (1, 0, pb * (1 - pa)),
                (0, 1, (1 - pb) * pa),
                (1, 1, pb * pa),
            ):
                if weight == 0 or mass * weight == 0:
                    # Only exact zeros or IEEE underflow vanish, never a user cutoff.
                    continue
                next_q = q + buy - sell
                capture = buy * bid_distance + sell * ask_distance
                p, m, s = following.get(next_q, (0.0, 0.0, 0.0))
                following[next_q] = (
                    p + weight * mass,
                    m + weight * (first + capture * mass),
                    s
                    + weight
                    * (
                        second
                        + 2 * capture * first
                        + (capture**2 + next_q**2 * cfg.sigma**2 * cfg.dt) * mass
                    ),
                )
        states = following
    mass = math.fsum(v[0] for v in states.values())
    mean = math.fsum(v[1] for v in states.values())
    second = math.fsum(v[2] for v in states.values())
    q_mean = math.fsum(q * v[0] for q, v in states.items())
    q_second = math.fsum(q * q * v[0] for q, v in states.items())
    if not math.isclose(mass, 1, abs_tol=1e-12, rel_tol=0):
        raise ArithmeticError("probability mass not conserved")
    variance, q_variance = second - mean**2, q_second - q_mean**2
    if variance < -1e-9 or q_variance < -1e-9:
        raise ArithmeticError("negative moment variance")
    # Permit only roundoff at zero, not materially negative variance.
    return ExactMoments(mean, max(0.0, variance), q_mean, max(0.0, q_variance), mass, exceedances)


def symmetric_moments(cfg: SimulationConfig) -> ExactMoments:
    """Closed-form check for a constant symmetric spread and independent sides."""
    if not cfg.symmetric or cfg.spread not in ("constant", "average"):
        raise ValueError("closed form requires a constant symmetric spread")
    h = 1 / cfg.k if cfg.gamma == 0 else math.log1p(cfg.gamma / cfg.k) / cfg.gamma
    if cfg.spread == "average":
        h += cfg.gamma * cfg.sigma**2 * cfg.horizon / 4
    p, exceeds = _probability(h, cfg)
    n = round(cfg.horizon / cfg.dt)
    v = 2 * p * (1 - p)
    return ExactMoments(
        2 * h * n * p,
        h * h * n * v + cfg.sigma**2 * cfg.dt * (n * cfg.q0**2 + v * n * (n + 1) / 2),
        float(cfg.q0),
        n * v,
        1.0,
        2 * n * int(exceeds),
    )


@dataclass(frozen=True, slots=True)
class DistributionMoments:
    """Central moments of terminal profit and inventory under the discrete law."""

    profit_mean: float
    profit_variance: float
    profit_mu4: float
    inventory_mean: float
    inventory_variance: float
    inventory_mu4: float
    expected_probability_exceedances: float

    @property
    def profit_kurtosis(self) -> float:
        return self.profit_mu4 / self.profit_variance**2

    @property
    def inventory_kurtosis(self) -> float:
        return self.inventory_mu4 / self.inventory_variance**2


def _central4(raw: list[float]) -> tuple[float, float, float]:
    m1, m2, m3, m4 = raw[1], raw[2], raw[3], raw[4]
    variance = m2 - m1 * m1
    mu4 = m4 - 4 * m1 * m3 + 6 * m1 * m1 * m2 - 3 * m1**4
    return m1, variance, mu4


def distribution_moments(cfg: SimulationConfig, shift: float = 0.0) -> DistributionMoments:
    """Raw profit moments up to order four, per inventory state, without paths.

    With X the accumulated profit less ``shift`` and increment D = c + q' * eps,
    eps = +/- sigma*sqrt(dt) independent of X, E[(X + D)^j] expands binomially.
    ``shift`` recentres the recurrence to limit cancellation; it cancels exactly
    in central moments. Written separately from ``exact_moments`` so the two
    recurrences check each other on their shared first two moments.
    """
    n = round(cfg.horizon / cfg.dt)
    h = cfg.sigma * math.sqrt(cfg.dt)
    eps = [1.0, 0.0, h * h, 0.0, h**4]
    base = 2 / cfg.k if cfg.gamma == 0 else 2 * math.log1p(cfg.gamma / cfg.k) / cfg.gamma
    binom = [[math.comb(j, i) for i in range(5)] for j in range(5)]
    states: dict[int, list[float]] = {cfg.q0: [(-shift) ** j for j in range(5)]}
    exceedances = 0.0
    for step in range(n):
        risk = cfg.gamma * cfg.sigma**2 * (cfg.horizon - step * cfg.dt)
        width = base
        if cfg.spread == "equation":
            width += risk
        elif cfg.spread == "average":
            width += cfg.gamma * cfg.sigma**2 * cfg.horizon / 2
        following: dict[int, list[float]] = {}
        for q, raw in states.items():
            skew = 0.0 if cfg.symmetric else q * risk
            bid_distance, ask_distance = width / 2 + skew, width / 2 - skew
            pb, bad_b = _probability(bid_distance, cfg)
            pa, bad_a = _probability(ask_distance, cfg)
            exceedances += raw[0] * (int(bad_b) + int(bad_a))
            for buy, sell, weight in (
                (0, 0, (1 - pb) * (1 - pa)),
                (1, 0, pb * (1 - pa)),
                (0, 1, (1 - pb) * pa),
                (1, 1, pb * pa),
            ):
                if weight == 0 or raw[0] * weight == 0:
                    continue
                nq = q + buy - sell
                c = buy * bid_distance + sell * ask_distance
                d = [
                    math.fsum(binom[i][m] * c ** (i - m) * nq**m * eps[m] for m in range(i + 1))
                    for i in range(5)
                ]
                target = following.setdefault(nq, [0.0] * 5)
                for j in range(5):
                    target[j] += weight * math.fsum(
                        binom[j][i] * raw[j - i] * d[i] for i in range(j + 1)
                    )
        states = following
    total = [math.fsum(v[j] for v in states.values()) for j in range(5)]
    if not math.isclose(total[0], 1, abs_tol=1e-12, rel_tol=0):
        raise ArithmeticError("probability mass not conserved")
    mean, variance, mu4 = _central4(total)
    q_raw = [math.fsum(q**j * v[0] for q, v in states.items()) for j in range(5)]
    q_mean, q_variance, q_mu4 = _central4(q_raw)
    if min(variance, q_variance, mu4, q_mu4) < -1e-9:
        raise ArithmeticError("negative even central moment")
    return DistributionMoments(
        mean + shift,
        max(variance, 0.0),
        max(mu4, 0.0),
        q_mean,
        max(q_variance, 0.0),
        max(q_mu4, 0.0),
        exceedances,
    )
