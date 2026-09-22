"""Source-grounded comparisons. A completed simulation is not a successful replication."""

import json
import tomllib
import traceback
from pathlib import Path

import numpy as np
import polars as pl
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from asaudit.logging import RunManifest, file_hash
from asaudit.sim.replication import SimulationConfig, SimulationResult, assess, bootstrap, simulate


class ExperimentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    seed: int = Field(default=20260922, ge=0)
    n_paths: int = Field(default=1000, ge=2)
    bootstrap_repeats: int = Field(default=2000, ge=100)


class Targets(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    spread: float = Field(validation_alias=AliasChoices("spread", "average_spread"))
    profit_mean: float
    profit_std: float = Field(gt=0)
    final_q_mean: float
    final_q_std: float = Field(gt=0)


class Table(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table: int
    page: int
    gamma: float
    inventory: Targets
    symmetric: Targets


class Reference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: dict[str, str | bool]
    simulation_params: dict[str, str | float]
    tables: list[Table] = Field(min_length=3, max_length=3)
    formulas_as_printed: dict[str, str]
    transcription_notes: list[str]

    @model_validator(mode="after")
    def complete_tables(self) -> "Reference":
        if [table.table for table in self.tables] != [1, 2, 3]:
            raise ValueError("reference must contain ordered unique tables 1, 2, 3")
        return self


def variance_ratio(
    inventory: SimulationResult,
    symmetric: SimulationResult,
    rng: np.random.Generator,
    repeats: int,
) -> dict[str, float]:
    n = len(inventory.profit)
    denominator = float(np.var(inventory.profit, ddof=1))
    if denominator <= 0:
        raise ValueError("variance ratio undefined for zero inventory-strategy variance")
    ratios = np.empty(repeats)
    for i in range(repeats):
        a = inventory.profit[rng.integers(0, n, n)]
        b = symmetric.profit[rng.integers(0, n, n)]
        va = float(np.var(a, ddof=1))
        if va <= 0:
            raise ValueError("bootstrap variance ratio undefined")
        ratios[i] = float(np.var(b, ddof=1)) / va
    low, high = np.quantile(ratios, [0.025, 0.975])
    return {
        "estimate": float(np.var(symmetric.profit, ddof=1)) / denominator,
        "low": float(low),
        "high": float(high),
    }


def run_replication(
    config: Path,
    reference: Path,
    output: Path,
    allow_dirty: bool,
) -> tuple[Path, bool]:
    plan = ExperimentPlan.model_validate(tomllib.loads(config.read_text()))
    golden = Reference.model_validate_json(reference.read_text())
    version = str(golden.source.get("version"))
    published = "10.1080/14697680701381228" in version
    if not published and "October 5, 2006" not in version:
        raise ValueError("unrecognized source version")
    source_version = "QF 2008 published article" if published else "2006-10-05 working paper"
    variants = (
        ("published_strict", "published_saturated")
        if published
        else ("equation_strict", "equation_saturated", "constant_saturated")
    )
    resolved: dict[str, object] = plan.model_dump(mode="json")
    resolved.update(
        reference=str(reference),
        protocol="qf2008-v1" if published else "working-paper-v1",
        probability_modes=["strict", "saturate"],
        spread_modes=["equation", "average"] if published else ["equation", "constant"],
        symmetric_spread="continuous time average" if published else "same as inventory",
        mid_update="binary",
        timing="old-state fills then mid move",
        bootstrap="pathwise percentile, 95% pointwise, ddof=1",
        variance_ratio="symmetric profit variance / inventory profit variance",
    )
    run = RunManifest(
        output, resolved, allow_dirty, "AS-2008-replication" if published else "AS-2006-replication"
    )
    run.document.update(
        seed=plan.seed,
        seed_reason="fixed before first experiment",
        data_checksums={str(p): file_hash(p) for p in (config, reference)},
    )
    run.write()
    experiments: list[dict[str, object]] = []
    streams: list[dict[str, object]] = []
    root = np.random.SeedSequence(plan.seed, spawn_key=(2008,) if published else ())
    # Fixed allocation independent of successes: 2 simulations, 2 bootstraps, 1 ratio per case.
    children = root.spawn(len(golden.tables) * len(variants) * 5)
    total_fills = 0
    primary_passes: list[bool] = []
    try:
        for table_index, table in enumerate(golden.tables):
            for variant_index, variant in enumerate(variants):
                offset = (table_index * len(variants) + variant_index) * 5
                case: dict[str, object] = {
                    "table": table.table,
                    "gamma": table.gamma,
                    "variant": variant,
                    "primary": variant_index == 0,
                }
                results: dict[str, SimulationResult] = {}
                passed: list[bool] = []
                for side_index, name in enumerate(("inventory", "symmetric")):
                    params = golden.simulation_params
                    cfg = SimulationConfig(
                        s0=float(params["s0"]),
                        horizon=float(params["T"]),
                        sigma=float(params["sigma"]),
                        dt=float(params["dt"]),
                        q0=int(params["q0"]),
                        gamma=table.gamma,
                        k=float(params["k"]),
                        A=float(params["A"]),
                        n_paths=plan.n_paths,
                        symmetric=side_index == 1,
                        spread=(
                            "average"
                            if published and side_index == 1
                            else "constant"
                            if variant_index == 2
                            else "equation"
                        ),
                        probability="strict" if variant_index == 0 else "saturate",
                    )
                    child = children[offset + side_index]
                    streams.append(
                        {
                            "case": f"{table.table}/{variant}/{name}",
                            "simulation_spawn_key": list(child.spawn_key),
                            "bootstrap_spawn_key": list(
                                children[offset + 2 + side_index].spawn_key
                            ),
                            "config": cfg.model_dump(mode="json"),
                        }
                    )
                    try:
                        result = simulate(cfg, child)
                    except ValueError as exc:
                        # Preserve invalid Bernoulli runs as failed cases; do not retry a seed.
                        if "fill probability" not in str(exc):
                            raise
                        case[name] = {"status": "invalid_probability", "error": str(exc)}
                        passed.append(False)
                        continue
                    results[name] = result
                    total_fills += result.n_fills
                    metrics = bootstrap(
                        result.profit,
                        result.inventory,
                        np.random.default_rng(children[offset + 2 + side_index]),
                        plan.bootstrap_repeats,
                    )
                    target = table.inventory if side_index == 0 else table.symmetric
                    checks = assess(metrics, target.model_dump())
                    passed.extend(checks.values())
                    filename = f"table{table.table}-{variant}-{name}.parquet"
                    pl.DataFrame(
                        {
                            "path": np.arange(plan.n_paths),
                            "profit": result.profit,
                            "final_q": result.inventory,
                            "terminal_mid": result.mid,
                        }
                    ).write_parquet(run.directory / filename)
                    case[name] = {
                        "status": "completed",
                        "metrics": metrics,
                        "target_inside_ci": checks,
                        "targets": target.model_dump(),
                        "probability_exceedances": result.probability_exceedances,
                        "max_raw_probability": result.max_probability,
                        "max_accounting_error": result.max_accounting_error,
                        "paths": filename,
                    }
                if len(results) == 2:
                    ratio = variance_ratio(
                        results["inventory"],
                        results["symmetric"],
                        np.random.default_rng(children[offset + 4]),
                        plan.bootstrap_repeats,
                    )
                    target_ratio = (table.symmetric.profit_std / table.inventory.profit_std) ** 2
                    relative_error = abs(ratio["estimate"] / target_ratio - 1)
                    case.update(
                        variance_ratio=ratio,
                        target_variance_ratio=target_ratio,
                        ratio_relative_error=relative_error,
                        ratio_within_ten_percent=relative_error <= 0.1,
                    )
                    passed.append(relative_error <= 0.1)
                case["all_checks_pass"] = bool(passed) and all(passed)
                if variant_index == 0:
                    primary_passes.append(bool(case["all_checks_pass"]))
                experiments.append(case)
        eligible = plan.n_paths == int(golden.simulation_params["n_simulations"])
        accepted = eligible and all(primary_passes)
        report: dict[str, object] = {
            "source_version": source_version,
            "accepted": accepted,
            "acceptance_eligible": eligible,
            "experiments": experiments,
            "interpretation": "Diagnostic variants cannot satisfy primary acceptance.",
            "limitations": [
                "Source table transcription is agent-checked, not human-verified.",
                "Pointwise intervals do not account for paper Monte Carlo uncertainty.",
                "Paper does not specify seeds, side dependence or probability overflow.",
            ],
        }
        target_path = run.directory / "comparison.json"
        target_path.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n")
        run.finish(
            "passed" if accepted else "not_reproduced",
            streams=streams,
            ratio_spawn_keys=[list(children[i].spawn_key) for i in range(4, len(children), 5)],
            n_fills=total_fills,
            n_events=0,
            output_checksums={p.name: file_hash(p) for p in sorted(run.directory.glob("*.parquet"))}
            | {"comparison.json": file_hash(target_path)},
            data_quality={"source": "synthetic experiment", "source_version": source_version},
        )
        return run.directory, accepted
    except Exception as exc:
        # Preserve unexpected implementation failures, not a successful scientific result.
        run.finish("failed", error=str(exc), traceback=traceback.format_exc(), streams=streams)
        raise
