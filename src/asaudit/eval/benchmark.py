"""Packaged benchmark: score any Quoter factory on the policy-fit episodes."""

import importlib
import json
import sys
import tomllib
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from asaudit.attribution.grid import ALL_CONFIGS
from asaudit.attribution.run import (
    AblationConfig,
    Runner,
    _policies_for,
    child,
    load_sessions,
    split_episodes,
)
from asaudit.calibration.bundle import calibrate
from asaudit.eval.bootstrap import stationary_bootstrap_mean
from asaudit.logging import RunManifest, file_hash
from asaudit.strategy.base import Quoter


def load_factory(spec: str) -> Callable[[int], Quoter]:
    module, _, attr = spec.partition(":")
    # Submissions live in the working tree (e.g. benchmarks/), not the installed package.
    if str(Path.cwd()) not in sys.path:
        sys.path.insert(0, str(Path.cwd()))
    if not module or not attr:
        raise ValueError("quoter spec must be 'package.module:factory'")
    factory = getattr(importlib.import_module(module), attr)
    if not callable(factory):
        raise TypeError(f"{spec} is not callable")
    return factory  # type: ignore[no-any-return]


def run_benchmark(spec: str, config: Path, output: Path, allow_dirty: bool) -> Path:
    cfg = AblationConfig.model_validate(tomllib.loads(config.read_text()))
    factory = load_factory(spec)
    run = RunManifest(
        output,
        {"quoter": spec, "ablation": cfg.model_dump(mode="json")},
        allow_dirty,
        f"benchmark/{spec}",
    )
    run.document.update(seed=cfg.seed, data_checksums={str(config): file_hash(config)})
    run.write()
    try:
        root = np.random.SeedSequence(cfg.seed)
        data_seed, fit_seed, boot_seed = (child(root, i) for i in range(3))
        rows: list[dict[str, Any]] = []
        for s_index, s in enumerate(load_sessions(cfg, data_seed)):
            cal_span, fit_eps, _, _ = split_episodes(s, cfg.data, child(data_seed, 1000 + s_index))
            cal = calibrate(
                [cal_span],
                np.random.default_rng(child(fit_seed, s_index)),
                cfg.sim.markout_horizon_ns,
            )
            runner = Runner(cfg, cal, s.tick)
            quoters: list[tuple[str, Quoter, int]] = [
                ("avellaneda_stoikov", runner.as_quoter(), 0),
                ("symmetric", runner.symmetric_quoter(), 1),
                ("submission", factory(s.tick), 4),
            ]
            for e in fit_eps:
                for g in ALL_CONFIGS:
                    for pol in _policies_for(g, cfg):
                        for name, q, stream in quoters:
                            r = runner.run(e, g, pol, q, stream)
                            rows.append(
                                {
                                    "grid": g.label,
                                    "policy": pol,
                                    "strategy": name,
                                    "pnl": r.pnl,
                                    "notional": r.notional,
                                }
                            )
        rng = np.random.default_rng(boot_seed)
        summary: dict[str, Any] = {}
        for g in ALL_CONFIGS:
            for pol in _policies_for(g, cfg):
                cell: dict[str, Any] = {}
                for name in ("avellaneda_stoikov", "symmetric", "submission"):
                    sel = [
                        r
                        for r in rows
                        if r["grid"] == g.label and r["policy"] == pol and r["strategy"] == name
                    ]
                    pnl = np.array([r["pnl"] for r in sel])
                    notional = float(sum(r["notional"] for r in sel))
                    ci = stationary_bootstrap_mean(pnl, rng, cfg.eval.bootstrap_repeats)
                    cell[name] = {
                        "mean_pnl": ci.estimate,
                        "ci": [ci.low, ci.high],
                        "pnl_bps_of_notional": (float(pnl.sum()) / notional * 1e4)
                        if notional > 0
                        else None,
                    }
                summary[f"{g.label}/{pol}"] = cell
        path = run.directory / "benchmark.json"
        path.write_text(
            json.dumps(
                {"fixture_output": cfg.data.source == "synthetic", "cells": summary},
                indent=2,
                allow_nan=False,
            )
            + "\n"
        )
        run.finish("completed", output_checksums={path.name: file_hash(path)})
        return run.directory
    except Exception as exc:
        run.finish("failed", error=str(exc), traceback=traceback.format_exc())
        raise
