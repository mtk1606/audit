import asyncio
import json
import time
import traceback
from dataclasses import asdict
from datetime import date as Date
from pathlib import Path
from typing import Annotated

import structlog
import typer

from asaudit.config import collector_config, validation_config
from asaudit.data.crypto_l3 import FullChannelRecorder, ParquetJournal, collect
from asaudit.data.lobster import SessionMetadata
from asaudit.data.quality import DataQualityError, validate_pair
from asaudit.logging import RunManifest, file_hash

app = typer.Typer(no_args_is_help=True)
data = typer.Typer(no_args_is_help=True)
app.add_typer(data, name="data")


def source_paths(root: Path, symbol: str, day: str, depth: int) -> tuple[Path, Path]:
    paths: list[Path] = []
    for kind in ("message", "orderbook"):
        candidates = sorted(root.glob(f"{symbol}_{day}_*_{kind}_{depth}.csv"))
        if len(candidates) != 1:
            raise ValueError(
                f"expected one {kind} CSV for {symbol} {day} depth={depth} "
                f"under {root}; found {len(candidates)}"
            )
        paths.append(candidates[0])
    return paths[0], paths[1]


@data.command("validate")
def validate(
    source: Annotated[str, typer.Option()] = "lobster",
    symbol: Annotated[str, typer.Option()] = "AAPL",
    date: Annotated[str, typer.Option()] = "2012-06-21",
    data_root: Annotated[Path, typer.Option()] = Path("data/raw/lobster"),
    output: Annotated[Path, typer.Option()] = Path("results"),
    config: Annotated[Path | None, typer.Option()] = None,
    allow_dirty: Annotated[bool, typer.Option()] = False,
) -> None:
    cfg = validation_config(config)
    resolved = cfg.model_dump(mode="json")
    resolved.update(source=source, symbol=symbol, date=date, data_root=str(data_root.resolve()))
    run = RunManifest(output, resolved, allow_dirty, f"{symbol}/{date}")
    log = structlog.get_logger("asaudit")
    try:
        if source != "lobster":
            raise ValueError("only lobster is supported by paired snapshot validation")
        metadata = SessionMetadata(
            symbol,
            Date.fromisoformat(date),
            cfg.depth,
            cfg.price_unit,
            cfg.timezone,
            cfg.timestamp_policy,
        )
        messages, books = source_paths(data_root, symbol, date, cfg.depth)
        run.document["data_checksums"] = {str(p): file_hash(p) for p in (messages, books)}
        run.write()
        report = validate_pair(messages, books, metadata, cfg.quality)
        run.finish("passed", data_quality=asdict(report), n_events=report.rows)
        log.info(
            "validation_passed", rows=report.rows, boundary_levels=report.supplied_boundary_levels
        )
        typer.echo(json.dumps(asdict(report), sort_keys=True, indent=2))
    except Exception as exc:
        # Top-level session boundary: persist traceback, then fail the command.
        if isinstance(exc, DataQualityError) and exc.report is not None:
            run.document["data_quality"] = asdict(exc.report)
            run.document["n_events"] = exc.report.rows
        run.finish("failed", error=str(exc), traceback=traceback.format_exc())
        log.error("validation_failed", error=str(exc))
        raise typer.Exit(1) from exc


@data.command("collect")
def collect_command(
    config: Annotated[Path, typer.Option()] = Path("configs/collector/coinbase.toml"),
    output: Annotated[Path, typer.Option()] = Path("results"),
    data_root: Annotated[Path, typer.Option()] = Path("data/raw/coinbase"),
    allow_dirty: Annotated[bool, typer.Option()] = False,
) -> None:
    cfg = collector_config(config)
    resolved = cfg.model_dump(mode="json")
    resolved["data_root"] = str(data_root.resolve())
    run = RunManifest(output, resolved, allow_dirty, cfg.symbol)
    sink = ParquetJournal(data_root, cfg.symbol, cfg.batch_size)
    recorder = FullChannelRecorder(cfg.symbol, sink)
    try:
        asyncio.run(
            collect(
                recorder,
                cfg.duration_seconds,
                cfg.max_reconnects,
                cfg.reconnect_seconds,
                cfg.queue_capacity,
                cfg.flush_seconds,
            )
        )
    except (Exception, KeyboardInterrupt) as exc:
        # Capture abort state, including user interruption, without hiding failure.
        recorder.close("aborted", time.time_ns())
        run.finish(
            "failed",
            error=str(exc),
            traceback=traceback.format_exc(),
            data_checksums={str(p): file_hash(p) for p in sink.paths},
            data_quality={
                "sequence_gaps": recorder.gaps,
                "discontinuities": recorder.discontinuities,
            },
            n_events=recorder.messages,
        )
        raise typer.Exit(1) from exc
    quality = {
        "sequence_gaps": recorder.gaps,
        "discontinuities": recorder.discontinuities,
        "segments": recorder.segments,
        "gap_free_run": recorder.discontinuities == 0 and recorder.gaps == 0,
    }
    if recorder.messages == 0:
        quality["gap_free_run"] = False
    run.finish(
        "passed" if quality["gap_free_run"] else "incomplete",
        data_quality=quality,
        data_checksums={str(p): file_hash(p) for p in sink.paths},
        n_events=recorder.messages,
    )
    typer.echo(json.dumps(quality, indent=2))
    if not quality["gap_free_run"]:
        raise typer.Exit(1)


@app.command("replicate")
def replicate(
    config: Annotated[Path, typer.Option()] = Path("configs/replication/working_paper.toml"),
    reference: Annotated[Path, typer.Option()] = Path("tests/golden/as2008_table.json"),
    output: Annotated[Path, typer.Option()] = Path("results"),
    allow_dirty: Annotated[bool, typer.Option()] = False,
) -> None:
    """Run the 2006 working-paper audit; exit 1 when replication criteria fail."""
    from asaudit.eval.replication import run_replication

    directory, accepted = run_replication(config, reference, output, allow_dirty)
    typer.echo(str(directory))
    if not accepted:
        raise typer.Exit(1)


@app.command("audit-moments")
def moments_command(
    source_manifest: Annotated[Path, typer.Option()] = Path(
        "docs/evidence/m1-qf2008/run/manifest.json"
    ),
    output: Annotated[Path, typer.Option()] = Path("results"),
    allow_dirty: Annotated[bool, typer.Option()] = False,
) -> None:
    """Independently calculate population moments of the declared discrete law."""
    from asaudit.eval.moments import audit_moments

    typer.echo(str(audit_moments(source_manifest, output, allow_dirty)))


@app.command("m1-sensitivity")
def sensitivity_command(
    config: Annotated[Path, typer.Option()] = Path("configs/replication/m1_sensitivity.toml"),
    reference: Annotated[Path, typer.Option()] = Path("tests/golden/as2008_table_qf2008.json"),
    output: Annotated[Path, typer.Option()] = Path("results"),
    allow_dirty: Annotated[bool, typer.Option()] = False,
) -> None:
    """Test printed paper values against exact sampling laws of each declared rule."""
    from asaudit.eval.sensitivity import run_sensitivity

    typer.echo(str(run_sensitivity(config, reference, output, allow_dirty)))


@app.command("ablate")
def ablate_command(
    config: Annotated[Path, typer.Option()] = Path("configs/ablation/fixture.toml"),
    output: Annotated[Path, typer.Option()] = Path("results"),
    allow_dirty: Annotated[bool, typer.Option()] = False,
    workers: Annotated[int, typer.Option(help="parallelism only; results are identical")] = 1,
) -> None:
    """Run the M3 ablation grid, walk-forward PolicyClassOptimum and attribution."""
    from asaudit.attribution.run import run_ablation

    directory, _ = run_ablation(config, output, allow_dirty, workers)
    typer.echo(str(directory))


@app.command("evaluate-holdout")
def holdout_command(
    config: Annotated[Path, typer.Option()],
    i_authorize_holdout: Annotated[bool, typer.Option("--i-authorize-holdout")] = False,
    rerun_reason: Annotated[str | None, typer.Option()] = None,
    output: Annotated[Path, typer.Option()] = Path("results"),
    allow_dirty: Annotated[bool, typer.Option()] = False,
) -> None:
    """M4: evaluate the corrected rule on held-out episodes. Touches the holdout once."""
    from asaudit.eval.holdout import run_holdout

    typer.echo(str(run_holdout(config, output, allow_dirty, i_authorize_holdout, rerun_reason)))


@app.command("benchmark")
def benchmark_command(
    quoter: Annotated[str, typer.Option(help="package.module:factory(tick) -> Quoter")],
    config: Annotated[Path, typer.Option()] = Path("configs/ablation/fixture.toml"),
    output: Annotated[Path, typer.Option()] = Path("results"),
    allow_dirty: Annotated[bool, typer.Option()] = False,
) -> None:
    """Score a third-party Quoter beside AS and the symmetric baseline."""
    from asaudit.eval.benchmark import run_benchmark

    typer.echo(str(run_benchmark(quoter, config, output, allow_dirty)))


@app.command("reproduce")
def reproduce_command(
    paper: Annotated[bool, typer.Option("--paper")] = False,
    fixture: Annotated[bool, typer.Option(help="synthetic data instead of LOBSTER")] = False,
    output: Annotated[Path, typer.Option()] = Path("results"),
    workers: Annotated[int, typer.Option()] = 1,
    allow_dirty: Annotated[bool, typer.Option()] = False,
) -> None:
    """Regenerate every reported table and figure (M1 evidence, then M3 attribution).

    The M4 holdout is deliberately excluded: it is run once, by hand, behind its gate.
    """
    if not paper:
        raise typer.BadParameter("pass --paper to regenerate the paper's outputs")
    from asaudit.attribution.run import run_ablation
    from asaudit.eval.moments import audit_moments
    from asaudit.eval.replication import run_replication
    from asaudit.eval.sensitivity import run_sensitivity

    reference = Path("tests/golden/as2008_table_qf2008.json")
    rep, accepted = run_replication(
        Path("configs/replication/qf2008.toml"), reference, output, allow_dirty
    )
    typer.echo(f"M1 published comparison (original contract, accepted={accepted}): {rep}")
    moments = audit_moments(Path("docs/evidence/m1-qf2008/run/manifest.json"), output, allow_dirty)
    typer.echo(f"M1 moments: {moments}")
    sensitivity = run_sensitivity(
        Path("configs/replication/m1_sensitivity.toml"), reference, output, allow_dirty
    )
    typer.echo(f"M1 sensitivity: {sensitivity}")
    ablation = Path("configs/ablation/fixture.toml" if fixture else "configs/ablation/lobster.toml")
    directory, _ = run_ablation(ablation, output, allow_dirty, workers)
    typer.echo(f"M3 attribution: {directory}")
