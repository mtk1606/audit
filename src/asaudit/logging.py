"""Run provenance and dual structured/human logging; not simulation accounting."""

import hashlib
import importlib.metadata
import json
import logging
import os
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import structlog


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def configure_logging(path: Path, run_id: str, session_id: str, config_hash: str) -> None:
    root = logging.getLogger("asaudit")
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    root.setLevel(logging.INFO)
    root.propagate = False
    file_handler = logging.FileHandler(path)
    file_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(processor=structlog.processors.JSONRenderer())
    )
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(processor=structlog.dev.ConsoleRenderer(colors=False))
    )
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        run_id=run_id, session_id=session_id, config_hash=config_hash
    )


class RunManifest:
    def __init__(
        self, output: Path, config: dict[str, object], allow_dirty: bool, session_id: str
    ) -> None:
        self.started = time.monotonic()
        encoded = json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False)
        config_hash = hashlib.sha256(encoded.encode()).hexdigest()
        git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
        sha = git.stdout.strip() if git.returncode == 0 else None
        tree = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        dirty = bool(tree.stdout.strip()) or tree.returncode != 0
        if (dirty or sha is None) and not allow_dirty:
            raise ValueError(
                "run requires a clean Git checkout; use --allow-dirty to record an exception"
            )
        now = datetime.now(UTC)
        run_id = (
            f"{now.strftime('%Y%m%dT%H%M%S%fZ')}_{(sha or 'no-git')[:10]}_"
            f"{config_hash[:10]}_{uuid4().hex[:8]}"
        )
        self.directory = output / run_id
        self.directory.mkdir(parents=True, exist_ok=False)
        env = {"python": platform.python_version(), "platform": platform.platform()}
        for name in ("numpy", "polars", "pydantic", "structlog", "websockets", "httpx", "typer"):
            env[name] = importlib.metadata.version(name)
        self.document: dict[str, object] = {
            "run_id": run_id,
            "git_sha": sha,
            "git_dirty": dirty,
            "allow_dirty": allow_dirty,
            "config_hash": config_hash,
            "config": config,
            "env": env,
            "started_utc": now.isoformat(),
            "finished_utc": None,
            "seed": None,
            "seed_reason": "M0 ingestion/validation has no random number generation",
            "data_checksums": {},
            "status": "running",
            "session_id": session_id,
            "data_quality": {},
            "n_events": 0,
            "n_fills": 0,
        }
        configure_logging(self.directory / "events.jsonl", run_id, session_id, config_hash)
        self.write()

    def write(self) -> None:
        target = self.directory / "manifest.json"
        tmp = target.with_suffix(".tmp")
        with tmp.open("w") as handle:
            json.dump(self.document, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)

    def finish(self, status: str, **fields: object) -> None:
        self.document.update(fields)
        self.document.update(
            status=status,
            finished_utc=datetime.now(UTC).isoformat(),
            elapsed_seconds=time.monotonic() - self.started,
        )
        self.write()
