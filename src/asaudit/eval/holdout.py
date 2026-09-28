"""M4 held-out evaluation of the corrected rule. Touch the holdout once.

Gate: the config must set ``holdout_authorized = true`` and the CLI must pass
``--i-authorize-holdout``. Every run appends to a committed ledger; a second
run on the same data key is refused unless a rerun reason is given, and that
reason is recorded. Evaluated in the fully empirical cell (A1, A2, A3 all on).
"""

import hashlib
import json
import tomllib
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

from asaudit.attribution.grid import GridConfig
from asaudit.attribution.run import (
    AblationConfig,
    Episode,
    Runner,
    child,
    holdout_episodes,
    load_sessions,
    split_episodes,
)
from asaudit.calibration.bundle import calibrate
from asaudit.eval.bootstrap import stationary_bootstrap_mean
from asaudit.eval.optimize import OptimizeResult, sep_cma_es
from asaudit.logging import RunManifest, file_hash
from asaudit.sim.engine import EngineConfig
from asaudit.sim.fills.queue import CancelPolicy
from asaudit.strategy.base import Quoter
from asaudit.strategy.corrected import CorrectedQuoter
from asaudit.strategy.policy_class import PolicySpace

FULL = GridConfig(True, True, True)
FloatArray = NDArray[np.float64]


class HoldoutConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    ablation_config: str
    holdout_authorized: bool = False
    ledger: str = "docs/evidence/holdout_ledger.json"
    quote_sizes: list[int] = Field(default=[1, 10, 100], min_length=1)


class HoldoutRefused(PermissionError):
    pass


def data_key(cfg: AblationConfig) -> str:
    blob = json.dumps(cfg.data.model_dump(mode="json"), sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def _check_ledger(path: Path, key: str, rerun_reason: str | None) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = json.loads(path.read_text()) if path.exists() else []
    if any(e["data_key"] == key for e in entries) and not rerun_reason:
        raise HoldoutRefused(
            f"holdout for data key {key} was already evaluated; pass a rerun reason to override"
        )
    return entries


def run_holdout(
    config: Path,
    output: Path,
    allow_dirty: bool,
    cli_authorized: bool,
    rerun_reason: str | None = None,
) -> Path:
    hc = HoldoutConfig.model_validate(tomllib.loads(config.read_text()))
    if not (hc.holdout_authorized and cli_authorized):
        raise HoldoutRefused("holdout needs holdout_authorized = true AND --i-authorize-holdout")
    ab_path = Path(hc.ablation_config)
    cfg = AblationConfig.model_validate(tomllib.loads(ab_path.read_text()))
    key = data_key(cfg)
    ledger = Path(hc.ledger)
    entries = _check_ledger(ledger, key, rerun_reason)
    run = RunManifest(
        output,
        hc.model_dump(mode="json") | {"ablation": cfg.model_dump(mode="json")},
        allow_dirty,
        f"{cfg.run_name}/holdout",
    )
    run.document.update(
        seed=cfg.seed,
        data_checksums={str(p): file_hash(p) for p in (config, ab_path)},
        holdout_data_key=key,
        rerun_reason=rerun_reason,
    )
    run.write()
    entries.append(
        {
            "data_key": key,
            "run_id": run.document["run_id"],
            "utc": datetime.now(UTC).isoformat(),
            "rerun_reason": rerun_reason,
        }
    )
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps(entries, indent=2) + "\n")
    try:
        report = _evaluate(cfg, hc)
        report["fixture_output"] = cfg.data.source == "synthetic"
        path = run.directory / "holdout.json"
        path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        run.finish("completed", output_checksums={path.name: file_hash(path)})
        return run.directory
    except Exception as exc:
        run.finish("failed", error=str(exc), traceback=traceback.format_exc())
        raise


def _evaluate(cfg: AblationConfig, hc: HoldoutConfig) -> dict[str, Any]:
    root = np.random.SeedSequence(cfg.seed)
    data_seed, fit_seed, boot_seed = (child(root, i) for i in range(3))
    sessions = load_sessions(cfg, data_seed)
    gamma_tick = cfg.strategies.as_gamma_per_tick
    rows: list[dict[str, Any]] = []
    for s_index, s in enumerate(sessions):
        sym_seed = child(data_seed, 1000 + s_index)
        cal_span, fit_eps, _, _ = split_episodes(s, cfg.data, sym_seed)
        held = holdout_episodes(s, cfg.data, sym_seed)
        cal = calibrate(
            [cal_span], np.random.default_rng(child(fit_seed, s_index)), cfg.sim.markout_horizon_ns
        )
        for size in hc.quote_sizes:
            runner = Runner(cfg, cal, s.tick)
            runner.engine_cfg = EngineConfig(
                latency_ns=cfg.sim.latency_ns,
                quote_size=size,
                max_inventory=cfg.sim.max_inventory * size,
                markout_horizon_ns=cfg.sim.markout_horizon_ns,
            )
            for policy in cfg.cancel_attribution:
                space = PolicySpace(
                    cfg.strategies.reference_class, max_inventory=cfg.sim.max_inventory
                )

                opt = _fit_reference(
                    runner, space, policy, fit_eps, cfg, child(fit_seed, 20_000 + s_index)
                )
                quoters: dict[str, Quoter] = {
                    "avellaneda_stoikov": runner.as_quoter(),
                    "pco": runner.policy_quoter(space, opt.x),
                }
                for q_term, a_term in ((True, False), (False, True), (True, True)):
                    cq = CorrectedQuoter(
                        gamma_tick / s.tick,
                        cal,
                        cfg.data.episode_s,
                        s.tick,
                        queue_term=q_term,
                        adverse_term=a_term,
                    )
                    quoters[cq.name] = cq
                for e in held:
                    for name, q in quoters.items():
                        r = runner.run(e, FULL, policy, q, 0)
                        rows.append(
                            {
                                "symbol": s.symbol,
                                "episode": e.index,
                                "size": size,
                                "cancel_policy": policy,
                                "strategy": name,
                                "pnl": r.pnl,
                                "notional": r.notional,
                                "n_fills": r.n_fills,
                                "pco_converged": opt.converged,
                            }
                        )
    return _summarise(rows, cfg, hc, np.random.default_rng(boot_seed))


def _fit_reference(
    runner: Runner,
    space: PolicySpace,
    policy: CancelPolicy,
    fit_eps: list[Episode],
    cfg: AblationConfig,
    seed: np.random.SeedSequence,
) -> OptimizeResult:
    """PolicyClassOptimum fitted on every policy-fit episode, never on the holdout."""

    def objective(theta: FloatArray) -> float:
        return float(
            np.mean(
                [
                    runner.run(e, FULL, policy, runner.policy_quoter(space, theta), 2).pnl
                    for e in fit_eps
                ]
            )
        )

    st = cfg.strategies
    return sep_cma_es(
        objective, space.initial(st.delta0), st.sigma0, st.budget, np.random.default_rng(seed)
    )


def _summarise(
    rows: list[dict[str, Any]], cfg: AblationConfig, hc: HoldoutConfig, rng: np.random.Generator
) -> dict[str, Any]:
    out: dict[str, Any] = {"cell": "A1=A2=A3=on", "results": {}}
    reps = cfg.eval.bootstrap_repeats
    for size in hc.quote_sizes:
        for policy in cfg.cancel_attribution:
            sel = [r for r in rows if r["size"] == size and r["cancel_policy"] == policy]
            keys = sorted({(r["symbol"], r["episode"]) for r in sel})
            pnl = {(r["symbol"], r["episode"], r["strategy"]): r["pnl"] for r in sel}
            res: dict[str, Any] = {}
            gap = np.array([pnl[(*k, "pco")] - pnl[(*k, "avellaneda_stoikov")] for k in keys])
            for name in ("corrected:queue", "corrected:adverse", "corrected:both"):
                gain = np.array([pnl[(*k, name)] - pnl[(*k, "avellaneda_stoikov")] for k in keys])
                ci = stationary_bootstrap_mean(gain, rng, reps) if len(gain) > 1 else None
                closure = float(gain.mean() / gap.mean()) if gap.mean() != 0 else None
                ratio_ci = _ratio_ci(gain, gap, rng, reps)
                res[name] = {
                    "mean_gain_vs_as": None if ci is None else ci.estimate,
                    "gain_ci": None if ci is None else [ci.low, ci.high],
                    "gain_excludes_zero": None if ci is None else ci.excludes_zero,
                    "shortfall_closure": closure,
                    "closure_ci": ratio_ci,
                }
            res["mean_gap_pco_minus_as"] = float(gap.mean()) if len(gap) else None
            res["n_episodes"] = len(keys)
            out["results"][f"size={size}/{policy}"] = res
    return out


def _ratio_ci(
    num: np.ndarray, den: np.ndarray, rng: np.random.Generator, reps: int
) -> list[float] | None:
    """Paired percentile bootstrap of mean(num) / mean(den) over episodes."""
    n = len(num)
    if n < 2:
        return None
    draws = []
    for _ in range(reps):
        idx = rng.integers(0, n, n)
        d = den[idx].mean()
        if d != 0:
            draws.append(num[idx].mean() / d)
    if len(draws) < reps * 0.9:
        return None  # denominator too often zero: ratio not estimable
    lo, hi = np.quantile(draws, [0.025, 0.975])
    return [float(lo), float(hi)]
