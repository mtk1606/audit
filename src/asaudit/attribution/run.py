"""M3 ablation runner: grid x strategies x episodes x cancel policies -> attribution.

Pipeline, per symbol:
  1. split time-ordered episodes into calibration / policy_fit / holdout;
     holdout episodes are never replayed or read for features;
  2. calibrate every mechanism on the contiguous calibration span;
  3. run AS and the symmetric benchmark on every policy_fit episode, for every
     grid cell and cancel policy (A1-off cells are policy independent);
  4. fit PolicyClassOptimum by expanding-window walk-forward and evaluate it
     out of sample on each test episode;
  5. gap_bps per test episode, exact Shapley over the grid, stationary block
     bootstrap CIs over episodes, pessimistic/optimistic bound intervals, and
     regime marginals.
The A2 attribution is written first in every output (PRD M3).
"""

import json
import math
import tomllib
import traceback
from collections import defaultdict
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

import numpy as np
import polars as pl
import structlog
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, model_validator

from asaudit.attribution.grid import ALL_CONFIGS, GridConfig, build_models
from asaudit.attribution.metrics import UndefinedMetric, gap_bps
from asaudit.attribution.shapley import shapley
from asaudit.calibration.bundle import Calibration, calibrate
from asaudit.data.lobster import SessionMetadata
from asaudit.data.regimes import EpisodeFeatures, episode_features, tercile, tercile_edges
from asaudit.data.replay import load_lobster_session
from asaudit.eval.bootstrap import BootstrapCI, stationary_bootstrap_mean
from asaudit.eval.optimize import OptimizeResult, sep_cma_es
from asaudit.eval.walkforward import walk_forward
from asaudit.logging import RunManifest, file_hash
from asaudit.sim.engine import Engine, EngineConfig, EpisodeResult, ReplaySource
from asaudit.sim.fills.queue import CancelPolicy
from asaudit.sim.session import ReplaySession
from asaudit.sim.synthetic import SyntheticConfig, generate_session
from asaudit.strategy.avellaneda_stoikov import ASQuoter
from asaudit.strategy.base import Quoter
from asaudit.strategy.policy_class import PolicyQuoter, PolicySpace
from asaudit.strategy.symmetric import SymmetricQuoter

FloatArray = NDArray[np.float64]
AXES_REPORT_ORDER = ("A2", "A1", "A3")


class DataSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source: Literal["synthetic", "lobster"]
    symbols: list[str] = Field(min_length=1)
    date: str = "2012-06-21"
    lobster_root: str = "data/raw/lobster"
    depth: int = 10
    session_start_s: float = 34_200.0
    session_end_s: float = 57_600.0
    episode_s: float = Field(default=300.0, gt=0)
    calibration: float = Field(default=0.4, gt=0, lt=1)
    policy_fit: float = Field(default=0.3, gt=0, lt=1)
    holdout: float = Field(default=0.3, ge=0, lt=1)
    synthetic_duration_s: float = 3600.0

    @model_validator(mode="after")
    def splits_sum_to_one(self) -> "DataSection":
        if not math.isclose(self.calibration + self.policy_fit + self.holdout, 1.0):
            raise ValueError("splits must sum to 1")
        return self


class SimSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    batch_ms: int = Field(default=100, gt=0)
    latency_ns: int = Field(default=100_000, ge=0)
    max_inventory: int = Field(default=20, ge=1)
    markout_horizon_ns: int = Field(default=1_000_000_000, gt=0)


class StrategySection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    as_gamma_per_tick: float = Field(default=0.01, ge=0)
    symmetric_half_spread_ticks: float = Field(default=0.5, ge=0)
    policy_classes: list[Literal["linear_skew", "tabular_binned"]] = ["linear_skew"]
    reference_class: Literal["linear_skew", "tabular_binned"] = "linear_skew"
    budget: int = Field(default=2000, ge=10)
    sigma0: float = Field(default=0.5, gt=0)
    delta0: float = Field(default=0.5, ge=0)


class EvalSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    bootstrap_repeats: int = Field(default=10_000, ge=100)
    min_train: int = Field(default=3, ge=1)
    allow_unconverged: bool = False


class AblationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_name: str
    seed: int = Field(ge=0)
    data: DataSection
    sim: SimSection = SimSection()
    cancel_attribution: list[CancelPolicy] = ["pessimistic", "uniform", "optimistic"]
    strategies: StrategySection = StrategySection()
    eval: EvalSection = EvalSection()

    @model_validator(mode="after")
    def reference_is_fitted(self) -> "AblationConfig":
        if self.strategies.reference_class not in self.strategies.policy_classes:
            raise ValueError("reference_class must be one of policy_classes")
        if "uniform" not in self.cancel_attribution:
            raise ValueError("uniform attribution is the headline and is required")
        return self


@dataclass(frozen=True, slots=True)
class Episode:
    symbol: str
    index: int
    session: ReplaySession
    seed: np.random.SeedSequence


def child(seq: np.random.SeedSequence, *keys: int) -> np.random.SeedSequence:
    """Deterministic child by explicit key. ``SeedSequence.spawn`` advances an
    internal counter, so repeated calls would silently break common random
    numbers across grid cells."""
    return np.random.SeedSequence(seq.entropy, spawn_key=(*seq.spawn_key, *keys))


def load_sessions(cfg: AblationConfig, root_seed: np.random.SeedSequence) -> list[ReplaySession]:
    d = cfg.data
    out: list[ReplaySession] = []
    for i, symbol in enumerate(d.symbols):
        child_seed = child(root_seed, i)
        if d.source == "synthetic":
            s = generate_session(
                SyntheticConfig(duration_s=d.synthetic_duration_s),
                np.random.default_rng(child_seed),
                f"{symbol}/synthetic",
                symbol=symbol,
            )
            out.append(s)
            continue
        root = Path(d.lobster_root)
        day = d.date
        msgs = sorted(root.glob(f"{symbol}_{day}_*_message_{d.depth}.csv"))
        books = sorted(root.glob(f"{symbol}_{day}_*_orderbook_{d.depth}.csv"))
        if len(msgs) != 1 or len(books) != 1:
            raise FileNotFoundError(f"expected one LOBSTER pair for {symbol} {day} in {root}")
        meta = SessionMetadata(symbol, date.fromisoformat(day), d.depth)
        full = load_lobster_session(msgs[0], books[0], meta)
        start = max(full.start_ns, _day_offset(full, d.session_start_s))
        end = min(full.end_ns, _day_offset(full, d.session_end_s))
        out.append(full.window(start, end, full.session_id))
    if len({x.symbol for x in out}) != len(out):
        # Episode keys are (symbol, index): duplicates would silently merge sessions.
        raise ValueError("session symbols must be unique")
    return out


def _day_offset(s: ReplaySession, seconds: float) -> int:
    """Absolute ns for ``seconds`` after the New York midnight of the session."""
    from asaudit.data.lobster import session_midnight_ns

    day = date.fromisoformat(s.session_id.split("/")[1])
    return session_midnight_ns(day) + int(seconds * 1e9)


def split_episodes(
    s: ReplaySession, cfg: DataSection, seed: np.random.SeedSequence
) -> tuple[ReplaySession, list[Episode], int, list[Episode]]:
    """Returns (calibration span, policy_fit episodes, holdout count, all non-holdout)."""
    width = int(cfg.episode_s * 1e9)
    n = (s.end_ns - s.start_ns) // width
    if n < 5:
        raise ValueError(f"{s.session_id}: fewer than five episodes")
    n_cal = max(1, round(n * cfg.calibration))
    n_fit = max(2, round(n * cfg.policy_fit))
    n_hold = n - n_cal - n_fit
    if n_hold < 0:
        raise ValueError("split leaves no room for policy_fit episodes")
    seeds = [child(seed, i) for i in range(n)]
    episodes = [
        Episode(
            s.symbol,
            i,
            s.window(s.start_ns + i * width, s.start_ns + (i + 1) * width, f"{s.session_id}#{i}"),
            seeds[i],
        )
        for i in range(n_cal + n_fit)
    ]
    cal_span = s.window(s.start_ns, s.start_ns + n_cal * width, f"{s.session_id}#cal")
    return cal_span, episodes[n_cal:], n_hold, episodes


def holdout_episodes(
    s: ReplaySession, cfg: DataSection, seed: np.random.SeedSequence
) -> list[Episode]:
    """The held-out tail. Only asaudit.eval.holdout may call this, behind its gate."""
    width = int(cfg.episode_s * 1e9)
    n = (s.end_ns - s.start_ns) // width
    n_cal = max(1, round(n * cfg.calibration))
    n_fit = max(2, round(n * cfg.policy_fit))
    return [
        Episode(
            s.symbol,
            i,
            s.window(s.start_ns + i * width, s.start_ns + (i + 1) * width, f"{s.session_id}#{i}"),
            child(seed, i),
        )
        for i in range(n_cal + n_fit, n)
    ]


class Runner:
    def __init__(self, cfg: AblationConfig, cal: Calibration, tick: int) -> None:
        self.cfg, self.cal, self.tick = cfg, cal, tick
        self.engine_cfg = EngineConfig(
            latency_ns=cfg.sim.latency_ns,
            max_inventory=cfg.sim.max_inventory,
            markout_horizon_ns=cfg.sim.markout_horizon_ns,
        )

    def run(
        self, e: Episode, g: GridConfig, policy: CancelPolicy, quoter: Quoter, stream: int
    ) -> EpisodeResult:
        fill, info, comp = build_models(g, self.cal, policy)
        s = e.session
        # Common random numbers: the stream depends on (episode, strategy) only.
        rng = np.random.default_rng(child(e.seed, stream))
        return Engine(self.engine_cfg, fill, info, comp).run(
            ReplaySource(s, self.cfg.sim.batch_ms * 1_000_000, s.start_ns, s.end_ns),
            quoter,
            rng,
            s.session_id,
        )

    def as_quoter(self) -> ASQuoter:
        st = self.cfg.strategies
        return ASQuoter(
            st.as_gamma_per_tick / self.tick,
            self.cal.sigma,
            self.cal.intensity.k,
            self.cfg.data.episode_s,
            self.tick,
        )

    def symmetric_quoter(self) -> SymmetricQuoter:
        return SymmetricQuoter(self.cfg.strategies.symmetric_half_spread_ticks, self.tick)

    def policy_quoter(self, space: PolicySpace, theta: FloatArray) -> PolicyQuoter:
        return PolicyQuoter(space, np.asarray(theta, dtype=np.float64), self.tick, self.cal.sigma)


def _policies_for(g: GridConfig, cfg: AblationConfig) -> list[CancelPolicy]:
    # A1-off cells have no queue, so every cancel policy is the same run.
    return list(cfg.cancel_attribution) if g.a1 else ["uniform"]


def _ci(values: list[float], rng: np.random.Generator, repeats: int) -> dict[str, float] | None:
    if len(values) < 2:
        return None
    ci: BootstrapCI = stationary_bootstrap_mean(np.asarray(values), rng, repeats)
    return asdict(ci) | {"excludes_zero": ci.excludes_zero}


@dataclass(frozen=True, slots=True)
class PreparedSymbol:
    symbol: str
    s_index: int
    runner: "Runner"
    fit_eps: list[Episode]
    n_holdout: int
    rows: list[dict[str, object]]
    features: dict[tuple[str, int], EpisodeFeatures]
    edges: dict[str, tuple[float, float]]
    calibration_summary: dict[str, float]


class _Serial:
    """Executor stand-in that keeps workers=1 runs in-process and debuggable."""

    def __enter__(self) -> "_Serial":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def map(self, fn: Any, *iterables: Any) -> Any:
        return map(fn, *iterables)


def _pool(workers: int) -> Any:
    if workers <= 1:
        return _Serial()
    return ProcessPoolExecutor(max_workers=workers)


def _prepare_symbol(
    cfg: AblationConfig,
    s_index: int,
    s: ReplaySession,
    data_seed: np.random.SeedSequence,
    fit_seed: np.random.SeedSequence,
) -> PreparedSymbol:
    cal_span, fit_eps, n_hold, visible = split_episodes(
        s, cfg.data, child(data_seed, 1000 + s_index)
    )
    cal = calibrate(
        [cal_span], np.random.default_rng(child(fit_seed, s_index)), cfg.sim.markout_horizon_ns
    )
    runner = Runner(cfg, cal, s.tick)
    feats = [episode_features(e.session, e.session.start_ns, e.session.end_ns) for e in visible]
    edges = {
        "spread": tercile_edges([f.spread_ticks for f in feats]),
        "volatility": tercile_edges([f.volatility for f in feats]),
        "depth": tercile_edges([f.depth for f in feats]),
    }
    rows: list[dict[str, object]] = []
    for e in fit_eps:
        for g in ALL_CONFIGS:
            for policy in _policies_for(g, cfg):
                quoters: list[tuple[str, Quoter]] = [
                    ("avellaneda_stoikov", runner.as_quoter()),
                    ("symmetric", runner.symmetric_quoter()),
                ]
                for stream, (name, q) in enumerate(quoters):
                    r = runner.run(e, g, policy, q, stream)
                    rows.append(_row(s.symbol, e.index, g, policy, name, r, "all"))
    summary = {
        "A": cal.intensity.A,
        "k": cal.intensity.k,
        "intensity_r2": cal.intensity.r2,
        "sigma": cal.sigma,
        "join_elasticity": cal.elasticity.join_elasticity,
        "join_se": cal.elasticity.join_se,
        "cancel_elasticity": cal.elasticity.cancel_elasticity,
        "cancel_se": cal.elasticity.cancel_se,
        "adverse_overall": cal.markout.overall,
    }
    return PreparedSymbol(
        s.symbol,
        s_index,
        runner,
        fit_eps,
        n_hold,
        rows,
        {(s.symbol, e.index): f for e, f in zip(visible, feats, strict=True)},
        edges,
        summary,
    )


def _pco_unit(
    cfg: AblationConfig,
    p: PreparedSymbol,
    klass: Literal["linear_skew", "tabular_binned"],
    g: GridConfig,
    policy: CancelPolicy,
    fit_seed: np.random.SeedSequence,
) -> tuple[list[dict[str, object]], list[dict[str, object]], int]:
    space = PolicySpace(klass, max_inventory=cfg.sim.max_inventory)
    folds = _fit_pco(
        p.runner, space, g, policy, p.fit_eps, cfg, child(fit_seed, 10_000 + p.s_index)
    )
    rows, out, bad = [], [], 0
    for fold in folds:
        e = p.fit_eps[fold.test_index]
        rows.append(_row(p.symbol, e.index, g, policy, f"pco:{klass}", fold.result, "test"))
        bad += int(not fold.converged)
        out.append(
            fold.summary()
            | {"symbol": p.symbol, "grid": g.label, "cancel_policy": policy, "klass": klass}
        )
    return rows, out, bad


def run_ablation(
    config: Path, output: Path, allow_dirty: bool, workers: int = 1
) -> tuple[Path, dict[str, Any]]:
    cfg = AblationConfig.model_validate(tomllib.loads(config.read_text()))
    run = RunManifest(output, cfg.model_dump(mode="json"), allow_dirty, cfg.run_name)
    log = structlog.get_logger("asaudit")
    root = np.random.SeedSequence(cfg.seed)
    data_seed, fit_seed, boot_seed = (child(root, i) for i in range(3))
    run.document.update(
        seed=cfg.seed,
        seed_reason="config seed; SeedSequence tree per symbol/"
        "episode/strategy; shared across grid cells (common random numbers)",
    )
    fixture = cfg.data.source == "synthetic"
    run.document["data_checksums"] = {str(config): file_hash(config)}
    run.write()
    try:
        sessions = load_sessions(cfg, data_seed)
        rows: list[dict[str, object]] = []
        folds_out: list[dict[str, object]] = []
        features: dict[tuple[str, int], EpisodeFeatures] = {}
        edges: dict[str, dict[str, tuple[float, float]]] = {}
        quality: dict[str, object] = {}
        not_converged = 0
        with _pool(workers) as pool:
            prepared = list(
                pool.map(
                    _prepare_symbol,
                    [cfg] * len(sessions),
                    range(len(sessions)),
                    sessions,
                    [data_seed] * len(sessions),
                    [fit_seed] * len(sessions),
                )
            )
            units = [
                (cfg, p, klass, g, policy, fit_seed)
                for p in prepared
                for klass in cfg.strategies.policy_classes
                for g in ALL_CONFIGS
                for policy in _policies_for(g, cfg)
            ]
            fitted = list(pool.map(_pco_unit, *zip(*units, strict=True)))
        holdout = 0
        for p in prepared:
            rows.extend(p.rows)
            features.update(p.features)
            edges[p.symbol] = p.edges
            holdout += p.n_holdout
            log.info("calibrated", symbol=p.symbol, **p.calibration_summary)
        quality["holdout_episodes_not_replayed"] = holdout
        quality["calibration"] = {p.symbol: p.calibration_summary for p in prepared}
        for unit_rows, unit_folds, unit_not_converged in fitted:
            rows.extend(unit_rows)
            folds_out.extend(unit_folds)
            not_converged += unit_not_converged
        frame = pl.DataFrame(rows)
        rows_path = run.directory / "episodes.parquet"
        frame.write_parquet(rows_path)
        report = _attribute(cfg, frame, features, edges, boot_seed)
        report.update(
            fixture_output=fixture,
            label="FIXTURE OUTPUT (synthetic data), not a market result"
            if fixture
            else "market replay result",
            pco_not_converged_folds=not_converged,
            allow_unconverged=cfg.eval.allow_unconverged,
            regime_edges={k: {a: list(b) for a, b in v.items()} for k, v in edges.items()},
        )
        att = run.directory / "attribution.json"
        att.write_text(json.dumps(report, indent=2, allow_nan=False, default=_json) + "\n")
        (run.directory / "pco_folds.json").write_text(
            json.dumps(folds_out, indent=2, allow_nan=False, default=_json) + "\n"
        )
        from asaudit.report.figures import attribution_figure

        fig = attribution_figure(report, run.directory / "attribution.png")
        status = "completed"
        if not_converged and not cfg.eval.allow_unconverged:
            status = "failed"
            log.error("pco_not_converged", folds=not_converged)
        run.finish(
            status,
            n_events=int(sum(s.n_events for s in sessions)),
            n_fills=int(frame["n_fills"].sum()),
            data_quality=quality,
            output_checksums={p.name: file_hash(p) for p in (rows_path, att, fig)},
        )
        if status == "failed":
            raise RuntimeError("policy-class optimisation did not converge (PRD 8 hard failure)")
        return run.directory, report
    except Exception as exc:
        if run.document.get("status") == "running":
            run.finish("failed", error=str(exc), traceback=traceback.format_exc())
        raise


def _json(x: object) -> object:
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, np.ndarray):
        return x.tolist()
    raise TypeError(f"not serializable: {type(x)}")


def _row(
    symbol: str,
    episode: int,
    g: GridConfig,
    policy: str,
    strategy: str,
    r: EpisodeResult,
    sample: str,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "episode": episode,
        "grid": g.label,
        "cancel_policy": policy,
        "strategy": strategy,
        "sample": sample,
        "pnl": r.pnl,
        "notional": r.notional,
        "n_fills": r.n_fills,
        "charges": r.charges,
        "inventory": r.inventory,
        "cap_hit_fraction": r.inventory_cap_hits / r.n_steps,
        "withheld_quotes": r.withheld_quotes,
    }


@dataclass(frozen=True, slots=True)
class PCOFold:
    test_index: int
    train_value: float
    test_value: float
    converged: bool
    evaluations: int
    params: list[float]
    result: EpisodeResult

    def summary(self) -> dict[str, object]:
        return {
            "test_index": self.test_index,
            "train_value": self.train_value,
            "test_value": self.test_value,
            "train_test_gap": self.train_value - self.test_value,
            "converged": self.converged,
            "evaluations": self.evaluations,
            "params": self.params,
        }


@dataclass(frozen=True, slots=True)
class EpisodeAttribution:
    symbol: str
    episode: int
    gap_000: float
    gap_111: float
    A1: float
    A2: float
    A3: float

    def get(self, axis: str) -> float:
        return float(getattr(self, axis))


def _fit_pco(
    runner: Runner,
    space: PolicySpace,
    g: GridConfig,
    policy: CancelPolicy,
    episodes: list[Episode],
    cfg: AblationConfig,
    fit_seed: np.random.SeedSequence,
) -> list[PCOFold]:
    st = cfg.strategies
    pco_stream = 2 + ["linear_skew", "tabular_binned"].index(space.klass)
    opt_seed = fit_seed  # same optimizer stream for every cell: paired comparisons

    def score(ep: Episode, theta: FloatArray) -> EpisodeResult:
        return runner.run(ep, g, policy, runner.policy_quoter(space, theta), pco_stream)

    def fit(train: Sequence[Episode], warm: FloatArray | None) -> OptimizeResult:
        def objective(theta: FloatArray) -> float:
            return float(np.mean([score(ep, theta).pnl for ep in train]))

        x0 = warm if warm is not None else space.initial(st.delta0)
        return sep_cma_es(objective, x0, st.sigma0, st.budget, np.random.default_rng(opt_seed))

    results: dict[int, EpisodeResult] = {}

    def evaluate(ep: Episode, theta: FloatArray) -> float:
        r = score(ep, theta)
        results[ep.index] = r
        return r.pnl

    folds = walk_forward(episodes, cfg.eval.min_train, fit, evaluate)
    return [
        PCOFold(
            f.test_index,
            f.train_value,
            f.test_value,
            f.converged,
            f.evaluations,
            f.params.tolist(),
            results[episodes[f.test_index].index],
        )
        for f in folds
    ]


def _attribute(
    cfg: AblationConfig,
    frame: pl.DataFrame,
    features: dict[tuple[str, int], EpisodeFeatures],
    edges: dict[str, dict[str, tuple[float, float]]],
    boot_seed: np.random.SeedSequence,
) -> dict[str, Any]:
    ref = f"pco:{cfg.strategies.reference_class}"
    reps = cfg.eval.bootstrap_repeats
    brng = np.random.default_rng(boot_seed)
    test = frame.filter(pl.col("strategy") == ref)
    test_keys = sorted({(r["symbol"], r["episode"]) for r in test.iter_rows(named=True)})
    lookup: dict[tuple[str, int, str, str, str], tuple[float, float]] = {
        (r["symbol"], r["episode"], r["grid"], r["cancel_policy"], r["strategy"]): (
            r["pnl"],
            r["notional"],
        )
        for r in frame.iter_rows(named=True)
    }

    def cell(sym: str, ep: int, grid: str, pol: str, strat: str) -> tuple[float, float]:
        key_pol = pol if grid[0] == "1" else "uniform"
        return lookup[(sym, ep, grid, key_pol, strat)]

    strategies: dict[str, Any] = {}
    undefined: dict[str, int] = defaultdict(int)
    for strat in ("avellaneda_stoikov", "symmetric"):
        per_policy: dict[str, dict[str, Any]] = {}
        for pol in cfg.cancel_attribution:
            totals: list[float] = []
            per_episode: list[EpisodeAttribution] = []
            for sym, ep in test_keys:
                try:
                    values = {
                        g.label: gap_bps(
                            cell(sym, ep, g.label, pol, ref)[0], *cell(sym, ep, g.label, pol, strat)
                        )
                        for g in ALL_CONFIGS
                    }
                except UndefinedMetric:
                    undefined[f"{strat}/{pol}"] += 1
                    continue
                phi = shapley(values)
                total = values["111"] - values["000"]
                if not math.isclose(sum(phi.values()), total, rel_tol=1e-9, abs_tol=1e-9):
                    raise ArithmeticError("Shapley efficiency violated")
                totals.append(total)
                per_episode.append(
                    EpisodeAttribution(
                        sym, ep, values["000"], values["111"], phi["A1"], phi["A2"], phi["A3"]
                    )
                )
            series = {a: [e.get(a) for e in per_episode] for a in AXES_REPORT_ORDER}
            series["total"] = totals
            per_policy[pol] = {
                "n_episodes": len(totals),
                "attribution_bps": {
                    a: _ci(series[a], brng, reps) for a in (*AXES_REPORT_ORDER, "total")
                },
                "per_symbol": _per_symbol(per_episode),
                "regimes": _regimes(per_episode, features, edges),
                "episodes": [asdict(e) for e in per_episode],
            }
        strategies[strat] = {
            "by_cancel_policy": per_policy,
            "bounds": _bounds(per_policy, cfg.cancel_attribution),
        }
    return {
        "reference": ref,
        "axes_order": list(AXES_REPORT_ORDER),
        "strategies": strategies,
        "undefined_gap_episodes": dict(undefined),
    }


def _per_symbol(per_episode: list[EpisodeAttribution]) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for sym in sorted({e.symbol for e in per_episode}):
        rows = [e for e in per_episode if e.symbol == sym]
        means = {a: float(np.mean([r.get(a) for r in rows])) for a in AXES_REPORT_ORDER}
        ranking = sorted(AXES_REPORT_ORDER, key=lambda a: -abs(means[a]))
        out[sym] = means | {"n": float(len(rows)), "rank": ",".join(ranking)}
    return out


def _regimes(
    per_episode: list[EpisodeAttribution],
    features: dict[tuple[str, int], EpisodeFeatures],
    edges: dict[str, dict[str, tuple[float, float]]],
) -> dict[str, Any]:
    tags: list[tuple[int, int, int]] = []
    for e in per_episode:
        f, ed = features[(e.symbol, e.episode)], edges[e.symbol]
        tags.append(
            (
                tercile(f.spread_ticks, ed["spread"]),
                tercile(f.volatility, ed["volatility"]),
                tercile(f.depth, ed["depth"]),
            )
        )
    paired = list(zip(per_episode, tags, strict=True))
    out: dict[str, Any] = {}
    for axis_i, axis in enumerate(("spread", "volatility", "depth")):
        out[axis] = {
            str(t): {
                a: _mean([e.get(a) for e, tg in paired if tg[axis_i] == t])
                for a in AXES_REPORT_ORDER
            }
            | {"n": sum(tg[axis_i] == t for tg in tags)}
            for t in range(3)
        }
    out["spread_x_volatility"] = {
        f"{i},{j}": {
            "n": sum(tg[0] == i and tg[1] == j for tg in tags),
            "A2": _mean([e.A2 for e, tg in paired if tg[0] == i and tg[1] == j]),
        }
        for i in range(3)
        for j in range(3)
    }
    return out


def _mean(xs: list[float]) -> float | None:
    return float(np.mean(xs)) if xs else None


def _bounds(per_policy: dict[str, dict[str, Any]], policies: Sequence[str]) -> dict[str, Any]:
    if not {"pessimistic", "optimistic"} <= set(policies):
        return {"available": False}
    out: dict[str, Any] = {"available": True}
    for a in (*AXES_REPORT_ORDER, "total"):
        est: dict[str, float | None] = {}
        for pol in ("pessimistic", "uniform", "optimistic"):
            ci = per_policy[pol]["attribution_bps"][a]
            est[pol] = None if ci is None else float(ci["estimate"])
        lo, hi = est["pessimistic"], est["optimistic"]
        flips = lo is not None and hi is not None and (lo > 0) != (hi > 0)
        out[a] = {
            "pessimistic": lo,
            "uniform": est["uniform"],
            "optimistic": hi,
            "sign_flips_across_bounds": flips,
            "headline_reportable": not flips,
        }
    return out
