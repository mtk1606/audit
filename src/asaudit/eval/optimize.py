"""Separable CMA-ES (Ros and Hansen 2008) for maximizing a noisy objective.

Deviation from the PRD's `cma_es`: the covariance is diagonal. Full CMA-ES is
quadratic in dimension, and tabular_binned has 270 parameters. Convergence is
declared when the best value improved by less than `rel_tol` over the last
`patience` generations; otherwise the result is marked not converged and the
caller must treat it as a hard failure (PRD 8).
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class OptimizeResult:
    x: FloatArray
    value: float
    evaluations: int
    generations: int
    converged: bool
    history: tuple[float, ...]


def sep_cma_es(
    objective: Callable[[FloatArray], float],
    x0: FloatArray,
    sigma0: float,
    budget: int,
    rng: np.random.Generator,
    *,
    patience: int = 8,
    rel_tol: float = 1e-3,
) -> OptimizeResult:
    n = len(x0)
    lam = 4 + int(3 * math.log(n))
    mu = lam // 2
    w = np.log(mu + 0.5) - np.log(np.arange(1, mu + 1))
    w /= w.sum()
    mu_eff = 1 / float(w @ w)
    c_sigma = (mu_eff + 2) / (n + mu_eff + 5)
    d_sigma = 1 + 2 * max(0.0, math.sqrt((mu_eff - 1) / (n + 1)) - 1) + c_sigma
    c_c = 4 / (n + 4)
    c_1 = 2 / ((n + 1.3) ** 2 + mu_eff) * (n + 2) / 3
    c_mu = min(1 - c_1, 2 * (mu_eff - 2 + 1 / mu_eff) / ((n + 2) ** 2 + mu_eff) * (n + 2) / 3)
    chi_n = math.sqrt(n) * (1 - 1 / (4 * n) + 1 / (21 * n * n))
    mean, sigma = x0.astype(np.float64).copy(), sigma0
    diag = np.ones(n)
    p_sigma, p_c = np.zeros(n), np.zeros(n)
    best_x, best_v = mean.copy(), objective(mean)
    evals, gen, history = 1, 0, [best_v]
    while evals + lam <= budget:
        gen += 1
        z = rng.standard_normal((lam, n))
        y = z * np.sqrt(diag)
        xs = mean + sigma * y
        values = np.array([objective(x) for x in xs])
        evals += lam
        if not np.isfinite(values).all():
            raise ArithmeticError("non-finite objective value")
        order = np.argsort(-values)  # maximize
        if values[order[0]] > best_v:
            best_v, best_x = float(values[order[0]]), xs[order[0]].copy()
        history.append(best_v)
        y_w = w @ y[order[:mu]]
        z_w = w @ z[order[:mu]]
        mean = mean + sigma * y_w
        p_sigma = (1 - c_sigma) * p_sigma + math.sqrt(c_sigma * (2 - c_sigma) * mu_eff) * z_w
        h = (
            float(np.linalg.norm(p_sigma)) / math.sqrt(1 - (1 - c_sigma) ** (2 * gen))
            < (1.4 + 2 / (n + 1)) * chi_n
        )
        p_c = (1 - c_c) * p_c + h * math.sqrt(c_c * (2 - c_c) * mu_eff) * y_w
        diag = (1 - c_1 - c_mu) * diag + c_1 * p_c**2 + c_mu * (w @ y[order[:mu]] ** 2)
        sigma *= math.exp((c_sigma / d_sigma) * (float(np.linalg.norm(p_sigma)) / chi_n - 1))
    converged = False
    if len(history) > patience:
        old = history[-patience - 1]
        converged = best_v - old <= rel_tol * (abs(best_v) + 1)
    return OptimizeResult(best_x, best_v, evals, gen, converged, tuple(history))
