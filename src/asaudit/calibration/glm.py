"""Iteratively reweighted least squares for Poisson and logistic GLMs.

Non-convergence raises (PRD 8: a non-converged fit is a hard failure).
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


class CalibrationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GLMFit:
    coef: FloatArray
    se: FloatArray
    iterations: int
    deviance: float
    n: int


def fit_glm(
    X: FloatArray,
    y: FloatArray,
    family: Literal["poisson", "logistic"],
    *,
    offset: FloatArray | None = None,
    ridge: float = 1e-8,
    max_iter: int = 100,
    tol: float = 1e-10,
) -> GLMFit:
    n, p = X.shape
    if n <= p or len(y) != n:
        raise CalibrationError(f"underdetermined GLM: n={n}, p={p}")
    if not (np.isfinite(X).all() and np.isfinite(y).all()):
        raise CalibrationError("non-finite GLM input")
    off = np.zeros(n) if offset is None else offset
    beta = np.zeros(p)
    if family == "poisson":
        beta[0] = float(np.log(max(y.mean(), 1e-12)))
    for it in range(1, max_iter + 1):
        eta = X @ beta + off
        if family == "poisson":
            mu = np.exp(np.clip(eta, -50, 50))
            w, z = mu, eta - off + (y - mu) / mu
        else:
            mu = 1 / (1 + np.exp(-np.clip(eta, -50, 50)))
            w = np.maximum(mu * (1 - mu), 1e-12)
            z = eta - off + (y - mu) / w
        info = X.T @ (w[:, None] * X) + ridge * np.eye(p)
        new = np.linalg.solve(info, X.T @ (w * z))
        if not np.isfinite(new).all():
            raise CalibrationError("GLM diverged")
        step = float(np.max(np.abs(new - beta)))
        beta = new
        if step < tol * (1 + float(np.max(np.abs(beta)))):
            eta = X @ beta + off
            if family == "poisson":
                mu = np.exp(eta)
                with np.errstate(divide="ignore", invalid="ignore"):
                    term = np.where(y > 0, y * np.log(y / mu), 0.0)
                deviance = float(2 * np.sum(term - (y - mu)))
                w = mu
            else:
                mu = 1 / (1 + np.exp(-eta))
                mu_c = np.clip(mu, 1e-15, 1 - 1e-15)
                deviance = float(-2 * np.sum(y * np.log(mu_c) + (1 - y) * np.log(1 - mu_c)))
                w = mu * (1 - mu)
            cov = np.linalg.inv(X.T @ (w[:, None] * X) + ridge * np.eye(p))
            return GLMFit(beta, np.sqrt(np.diag(cov)), it, deviance, n)
    raise CalibrationError(f"GLM did not converge in {max_iter} iterations")
