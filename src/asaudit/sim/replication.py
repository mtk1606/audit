"""Discrete working-paper experiment with explicit, auditable interpretation choices."""

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, model_validator

from asaudit.strategy.avellaneda_stoikov import liquidity_spread

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
BoolArray = NDArray[np.bool_]


class SimulationConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    s0: float = 100
    horizon: float = Field(default=1, gt=0)
    sigma: float = Field(default=2, ge=0)
    dt: float = Field(default=0.005, gt=0)
    q0: int = 0
    gamma: float = Field(default=0.1, ge=0)
    k: float = Field(default=1.5, gt=0)
    A: float = Field(default=140, ge=0)
    n_paths: int = Field(default=1000, ge=2)
    symmetric: bool = False
    spread: Literal["equation", "constant", "average"] = "equation"
    probability: Literal["strict", "saturate", "poisson"] = "strict"

    @model_validator(mode="after")
    def grid(self) -> "SimulationConfig":
        steps = self.horizon / self.dt
        if not math.isclose(steps, round(steps), abs_tol=1e-10, rel_tol=0) or steps < 1:
            raise ValueError("horizon must be an integral number of time steps")
        return self


@dataclass(frozen=True, slots=True)
class SimulationResult:
    profit: FloatArray
    inventory: IntArray
    mid: FloatArray
    probability_exceedances: int
    max_probability: float
    n_fills: int
    max_accounting_error: float


def advance(
    cash: FloatArray,
    inventory: IntArray,
    bid: FloatArray,
    ask: FloatArray,
    buy: BoolArray,
    sell: BoolArray,
    next_mid: FloatArray,
) -> tuple[FloatArray, IntArray, FloatArray]:
    next_cash = cash + sell * ask - buy * bid
    next_inventory = inventory + buy.astype(np.int64) - sell.astype(np.int64)
    return next_cash, next_inventory, next_cash + next_inventory * next_mid


def simulate(cfg: SimulationConfig, seed: np.random.SeedSequence) -> SimulationResult:
    """Both sides use pre-step inventory and quotes; fills precede the mid move.

    Strict mode rejects lambda*dt > 1. Saturation is a labelled diagnostic,
    never an implicit repair. Poisson mode uses 1 - exp(-lambda*dt), the
    probability of at least one arrival in dt. Bid/ask draws are independent.
    """
    rng = np.random.default_rng(seed)
    mid = np.full(cfg.n_paths, cfg.s0, dtype=np.float64)
    cash = np.zeros(cfg.n_paths, dtype=np.float64)
    q = np.full(cfg.n_paths, cfg.q0, dtype=np.int64)
    initial_value = cfg.q0 * cfg.s0
    pnl = np.zeros(cfg.n_paths, dtype=np.float64)
    cumulative = np.zeros(cfg.n_paths, dtype=np.float64)
    exceedances, n_fills = 0, 0
    max_probability, max_error = 0.0, 0.0
    for step in range(round(cfg.horizon / cfg.dt)):
        risk = cfg.gamma * cfg.sigma**2 * (cfg.horizon - step * cfg.dt)
        spread = liquidity_spread(cfg.gamma, cfg.k)
        if cfg.spread == "equation":
            spread += risk
        elif cfg.spread == "average":
            spread += cfg.gamma * cfg.sigma**2 * cfg.horizon / 2
        center = mid if cfg.symmetric else mid - q * risk
        bid, ask = center - spread / 2, center + spread / 2
        with np.errstate(over="raise", invalid="raise"):
            pa = cfg.A * np.exp(-cfg.k * (ask - mid)) * cfg.dt
            pb = cfg.A * np.exp(-cfg.k * (mid - bid)) * cfg.dt
        count = int(np.count_nonzero(pa > 1) + np.count_nonzero(pb > 1))
        if cfg.probability == "poisson":
            # Exceedances stay counted for diagnostics; this rule is always valid.
            pa, pb = -np.expm1(-pa), -np.expm1(-pb)
        exceedances += count
        max_probability = max(max_probability, float(pa.max()), float(pb.max()))
        if count and cfg.probability == "strict":
            raise ValueError(f"invalid fill probability at step {step}: {max_probability}")
        draws = rng.random((cfg.n_paths, 3))
        buy, sell = draws[:, 0] < np.minimum(pb, 1), draws[:, 1] < np.minimum(pa, 1)
        next_mid = mid + np.where(draws[:, 2] < 0.5, -1, 1) * cfg.sigma * math.sqrt(cfg.dt)
        old_q = q
        cash, q, wealth = advance(cash, q, bid, ask, buy, sell, next_mid)
        # Independent economic decomposition: spread capture plus inventory markout.
        cumulative += buy * (mid - bid) + sell * (ask - mid) + q * (next_mid - mid)
        pnl = wealth - initial_value
        error = float(np.max(np.abs(cumulative - pnl)))
        max_error = max(max_error, error)
        if not np.isfinite(pnl).all() or not np.allclose(cumulative, pnl, atol=1e-9, rtol=1e-12):
            raise ArithmeticError(f"accounting identity failed at step {step}")
        if not np.array_equal(q - old_q, buy.astype(np.int64) - sell.astype(np.int64)):
            raise ArithmeticError("inventory conservation failed")
        n_fills += int(np.count_nonzero(buy) + np.count_nonzero(sell))
        mid = next_mid
    for arr in (pnl, q, mid):
        arr.setflags(write=False)
    return SimulationResult(pnl, q, mid, exceedances, max_probability, n_fills, max_error)


def bootstrap(
    profit: FloatArray,
    inventory: IntArray,
    rng: np.random.Generator,
    repeats: int,
) -> dict[str, dict[str, float]]:
    """Pointwise percentile 95% intervals; independent paths are resampling units."""
    if len(profit) != len(inventory) or len(profit) < 2 or repeats < 2:
        raise ValueError("invalid bootstrap dimensions")
    metrics: dict[str, dict[str, float]] = {}
    # Reuse path indices for all metrics to preserve within-path dependence.
    indices = rng.integers(0, len(profit), size=(repeats, len(profit)))
    for label, values in (("profit", profit), ("final_q", inventory)):
        samples = values[indices]
        for statistic in ("mean", "std"):
            draws = samples.mean(axis=1) if statistic == "mean" else samples.std(axis=1, ddof=1)
            point = float(values.mean() if statistic == "mean" else values.std(ddof=1))
            low, high = np.quantile(draws, [0.025, 0.975])
            metrics[f"{label}_{statistic}"] = {
                "estimate": point,
                "low": float(low),
                "high": float(high),
            }
    return metrics


def assess(metrics: dict[str, dict[str, float]], targets: dict[str, float]) -> dict[str, bool]:
    return {
        name: metrics[name]["low"] <= target <= metrics[name]["high"]
        for name, target in targets.items()
        if name != "spread"
    }
