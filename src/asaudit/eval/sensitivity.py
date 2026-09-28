"""M1 sensitivity study: test printed paper values against exact sampling laws.

The paper reports one n=1000 Monte Carlo sample per cell. Under a declared
discrete law, the population moments are computable exactly, so the paper's
own sampling error (not ours) sets the tolerance. See DECISIONS 2026-09-28.
"""

import json
import math
import tomllib
import traceback
from pathlib import Path
from statistics import NormalDist
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from asaudit.eval.replication import Reference, Targets
from asaudit.logging import RunManifest, file_hash
from asaudit.sim.moments import DistributionMoments, distribution_moments, exact_moments
from asaudit.sim.replication import SimulationConfig

Rule = Literal["strict", "saturate", "poisson"]
METRICS = ("profit_mean", "profit_std", "final_q_mean", "final_q_std")
# Printed resolution of each metric in Tables 1-3.
RESOLUTION = {"profit_mean": 0.1, "profit_std": 0.1, "final_q_mean": 0.01, "final_q_std": 0.1}


class SensitivityPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    probability_rules: list[Rule] = Field(min_length=1)
    dts: list[float] = Field(min_length=1)
    acceptance_dt: float
    paper_n: int = Field(ge=2)
    family_alpha: float = Field(gt=0, lt=1)


def rounding_variance(resolution: float) -> float:
    return resolution**2 / 12


def metric_tests(m: DistributionMoments, target: Targets, n: int) -> dict[str, dict[str, float]]:
    """z-scores of printed values against the sampling law of an n-path estimate."""
    sd, q_sd = math.sqrt(m.profit_variance), math.sqrt(m.inventory_variance)
    population = {
        "profit_mean": m.profit_mean,
        "profit_std": sd,
        "final_q_mean": m.inventory_mean,
        "final_q_std": q_sd,
    }
    sampling_var = {
        "profit_mean": m.profit_variance / n,
        # Delta method: Var(s) ~ sigma^2 (kurtosis - 1) / (4n).
        "profit_std": m.profit_variance * (m.profit_kurtosis - 1) / (4 * n),
        "final_q_mean": m.inventory_variance / n,
        "final_q_std": m.inventory_variance * (m.inventory_kurtosis - 1) / (4 * n),
    }
    out: dict[str, dict[str, float]] = {}
    for name in METRICS:
        printed = float(getattr(target, name))
        se = math.sqrt(sampling_var[name] + rounding_variance(RESOLUTION[name]))
        out[name] = {
            "paper": printed,
            "population": population[name],
            "se": se,
            "z": (printed - population[name]) / se,
        }
    return out


def ratio_test(
    inv: DistributionMoments,
    sym: DistributionMoments,
    table_inv: Targets,
    table_sym: Targets,
    n: int,
) -> dict[str, float]:
    """z on log variance ratio; independent samples for the two strategies."""
    printed = (table_sym.profit_std / table_inv.profit_std) ** 2
    population = sym.profit_variance / inv.profit_variance
    rounding = (
        4 * rounding_variance(0.1) * (1 / table_sym.profit_std**2 + 1 / table_inv.profit_std**2)
    )
    var = (sym.profit_kurtosis - 1) / n + (inv.profit_kurtosis - 1) / n + rounding
    se = math.sqrt(var)
    return {
        "paper": printed,
        "population": population,
        "se_log": se,
        "z": (math.log(printed) - math.log(population)) / se,
        "relative_deviation": abs(population / printed - 1),
    }


def evaluate(
    reference: Reference, rule: Rule, dt: float, n: int
) -> tuple[dict[str, object], list[float]]:
    params = reference.simulation_params
    tables: list[dict[str, object]] = []
    zs: list[float] = []
    invalid: list[str] = []
    for table in reference.tables:
        row: dict[str, object] = {"table": table.table, "gamma": table.gamma}
        moments: dict[str, DistributionMoments] = {}
        for name, target in (("inventory", table.inventory), ("symmetric", table.symmetric)):
            cfg = SimulationConfig(
                s0=float(params["s0"]),
                horizon=float(params["T"]),
                sigma=float(params["sigma"]),
                dt=dt,
                q0=int(params["q0"]),
                gamma=table.gamma,
                k=float(params["k"]),
                A=float(params["A"]),
                symmetric=name == "symmetric",
                spread="average" if name == "symmetric" else "equation",
                probability=rule,
            )
            try:
                shift = exact_moments(cfg).profit_mean
                m = distribution_moments(cfg, shift=shift)
            except ValueError as exc:
                if "probability" not in str(exc):
                    raise
                row[name] = {"status": "invalid_probability", "error": str(exc)}
                invalid.append(f"{table.table}/{name}")
                continue
            moments[name] = m
            tests = metric_tests(m, target, n)
            zs.extend(t["z"] for t in tests.values())
            row[name] = {
                "status": "completed",
                "tests": tests,
                "profit_kurtosis": m.profit_kurtosis,
                "inventory_kurtosis": m.inventory_kurtosis,
                "expected_probability_exceedances": m.expected_probability_exceedances,
            }
        if len(moments) == 2:
            ratio = ratio_test(
                moments["inventory"], moments["symmetric"], table.inventory, table.symmetric, n
            )
            zs.append(ratio["z"])
            row["variance_ratio"] = ratio
        tables.append(row)
    return {"rule": rule, "dt": dt, "tables": tables, "invalid": invalid}, zs


def run_sensitivity(config: Path, reference: Path, output: Path, allow_dirty: bool) -> Path:
    plan = SensitivityPlan.model_validate(tomllib.loads(config.read_text()))
    golden = Reference.model_validate_json(reference.read_text())
    family = 3 * 2 * len(METRICS) + 3
    threshold = NormalDist().inv_cdf(1 - plan.family_alpha / (2 * family))
    run = RunManifest(
        output,
        plan.model_dump(mode="json") | {"reference": str(reference), "family_size": family},
        allow_dirty,
        "m1-sensitivity",
    )
    run.document.update(
        seed=None,
        seed_reason="deterministic calculation; no random draws",
        data_checksums={str(p): file_hash(p) for p in (config, reference)},
    )
    run.write()
    try:
        results: list[dict[str, object]] = []
        for dt in plan.dts:
            for rule in plan.probability_rules:
                result, raw = evaluate(golden, rule, dt, plan.paper_n)
                zs = [abs(z) for z in raw]
                complete = not result["invalid"] and len(zs) == family
                result.update(
                    tests_run=len(zs),
                    max_abs_z=max(zs) if zs else None,
                    failures=sum(z > threshold for z in zs),
                    consistent=complete and all(z <= threshold for z in zs),
                    acceptance_candidate=dt == plan.acceptance_dt,
                )
                results.append(result)
        consistent = [r["rule"] for r in results if r["acceptance_candidate"] and r["consistent"]]
        report: dict[str, object] = {
            "method": "exact population moments; paper n=1000 sampling error; Bonferroni",
            "family_size": family,
            "threshold_abs_z": threshold,
            "consistent_rules_at_paper_dt": consistent,
            "results": results,
            "scope": "tests the declared discrete law, not the authors' unpublished code",
        }
        path = run.directory / "sensitivity.json"
        path.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n")
        run.finish(
            "completed",
            output_checksums={path.name: file_hash(path)},
            data_quality={"source": "deterministic calculation"},
        )
        return run.directory
    except Exception as exc:
        run.finish("failed", error=str(exc), traceback=traceback.format_exc())
        raise
