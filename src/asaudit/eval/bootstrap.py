"""Stationary block bootstrap (Politis-Romano 1994) with the Politis-White
(2004) automatic block length, as corrected by Patton, Politis and White (2009).

Resampling units are sessions in time order. Blocks have geometric lengths with
mean b; indices wrap circularly.
"""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class BootstrapCI:
    estimate: float
    low: float
    high: float
    block_length: float
    n: int
    repeats: int

    @property
    def excludes_zero(self) -> bool:
        return self.low > 0 or self.high < 0


def _autocov(x: FloatArray, k: int) -> float:
    n = len(x)
    xc = x - x.mean()
    return float(xc[: n - k] @ xc[k:]) / n


def politis_white_block_length(x: FloatArray) -> float:
    """Optimal expected block length for the stationary bootstrap (b_SB)."""
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    if n < 4:
        return 1.0
    kn = max(5, math.ceil(math.sqrt(math.log10(n))))
    max_lag = min(n - 1, math.ceil(math.sqrt(n)) + kn)
    gamma0 = _autocov(x, 0)
    if gamma0 <= 0:
        return 1.0
    rho = np.array([_autocov(x, k) / gamma0 for k in range(1, max_lag + 1)])
    threshold = 2 * math.sqrt(math.log10(n) / n)
    m_hat = max_lag  # default when no run of insignificant lags is found
    for m in range(1, max_lag - kn + 2):
        if np.all(np.abs(rho[m - 1 : m - 1 + kn]) < threshold):
            m_hat = m - 1
            break
    big_m = min(2 * max(m_hat, 1), max_lag)
    g_hat, lr = 0.0, gamma0
    for k in range(1, big_m + 1):
        t = k / big_m
        weight = 1.0 if t <= 0.5 else 2 * (1 - t)
        gk = _autocov(x, k)
        g_hat += 2 * weight * k * gk
        lr += 2 * weight * gk
    d_sb = 2 * lr**2
    b_max = math.ceil(min(3 * math.sqrt(n), n / 3))
    if d_sb <= 0 or g_hat == 0:
        return 1.0
    b = (2 * g_hat**2 / d_sb) ** (1 / 3) * n ** (1 / 3)
    return float(min(max(b, 1.0), b_max))


def stationary_indices(n: int, block: float, rng: np.random.Generator) -> NDArray[np.int64]:
    p = 1 / block
    idx = np.empty(n, dtype=np.int64)
    idx[0] = rng.integers(n)
    starts = rng.random(n) < p
    fresh = rng.integers(0, n, size=n)
    for i in range(1, n):
        idx[i] = fresh[i] if starts[i] else (idx[i - 1] + 1) % n
    return idx


def stationary_bootstrap_mean(
    x: FloatArray, rng: np.random.Generator, repeats: int = 10_000, level: float = 0.95
) -> BootstrapCI:
    """Percentile CI for the mean of a time-ordered series of session values."""
    x = np.asarray(x, dtype=np.float64)
    if len(x) < 2 or not np.isfinite(x).all():
        raise ValueError("bootstrap needs at least two finite observations")
    block = politis_white_block_length(x)
    stats = np.empty(repeats)
    for r in range(repeats):
        stats[r] = x[stationary_indices(len(x), block, rng)].mean()
    alpha = (1 - level) / 2
    low, high = np.quantile(stats, [alpha, 1 - alpha])
    return BootstrapCI(float(x.mean()), float(low), float(high), block, len(x), repeats)
