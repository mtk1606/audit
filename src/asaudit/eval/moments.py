"""Traceable deterministic audit of the already-recorded published protocol."""

import json
import math
import traceback
from dataclasses import asdict
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from asaudit.logging import RunManifest, file_hash
from asaudit.sim.moments import exact_moments, symmetric_moments
from asaudit.sim.replication import SimulationConfig


class RecordedStream(BaseModel):
    model_config = ConfigDict(extra="ignore")
    case: str
    config: SimulationConfig


class RecordedRun(BaseModel):
    model_config = ConfigDict(extra="ignore")
    streams: list[RecordedStream]


def audit_moments(source_manifest: Path, output: Path, allow_dirty: bool) -> Path:
    source = RecordedRun.model_validate_json(source_manifest.read_text())
    streams = [s for s in source.streams if "/published_saturated/" in s.case]
    expected = {
        f"{i}/published_saturated/{name}" for i in (1, 2, 3) for name in ("inventory", "symmetric")
    }
    if len(streams) != 6 or {s.case for s in streams} != expected:
        raise ValueError("expected six unique published diagnostic configurations")
    run = RunManifest(
        output,
        {
            "method": "finite-state first and second moment recurrence",
            "source_manifest": str(source_manifest),
        },
        allow_dirty,
        "discrete-law-moment-audit",
    )
    run.document.update(
        seed=None,
        seed_reason="deterministic calculation; no random draws",
        data_checksums={str(source_manifest): file_hash(source_manifest)},
    )
    run.write()
    rows: list[dict[str, object]] = []
    try:
        for stream in streams:
            cfg = stream.config
            if cfg.probability != "saturate":
                raise ValueError("diagnostic stream must explicitly use saturation")
            moments = exact_moments(cfg)
            row: dict[str, object] = {
                "case": stream.case,
                "config": cfg.model_dump(mode="json"),
                "moments": asdict(moments),
                "profit_std": math.sqrt(moments.profit_variance),
                "final_q_std": math.sqrt(moments.inventory_variance),
            }
            if cfg.symmetric:
                closed = symmetric_moments(cfg)
                differences = {k: abs(v - asdict(closed)[k]) for k, v in asdict(moments).items()}
                if max(differences.values()) > 1e-8:
                    raise ArithmeticError("closed form disagrees with recurrence")
                row["closed_form_absolute_errors"] = differences
            rows.append(row)
        report: dict[str, object] = {
            "method": "population moments, float64 arithmetic, no inventory truncation",
            "confidence_intervals": "not applicable to deterministic population moments",
            "scope": "declared capped-Bernoulli law, not proof of author implementation",
            "rows": rows,
        }
        path = run.directory / "moments.json"
        path.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n")
        run.finish(
            "completed",
            output_checksums={path.name: file_hash(path)},
            data_quality={"configurations": len(rows), "inventory_cutoff": None},
        )
        return run.directory
    except Exception as exc:
        run.finish("failed", error=str(exc), traceback=traceback.format_exc())
        raise
