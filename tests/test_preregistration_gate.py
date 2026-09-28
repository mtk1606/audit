"""Market-data runs are refused until PREREGISTRATION.md is committed and tagged."""

import subprocess

import numpy as np
import pytest

from asaudit.attribution.run import (
    AblationConfig,
    PreregistrationRequired,
    load_sessions,
    require_preregistration,
)

LOBSTER = {"run_name": "x", "seed": 1, "data": {"source": "lobster", "symbols": ["AAPL"]}}


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_market_run_refused_without_preregistration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(PreregistrationRequired, match="not found"):
        load_sessions(AblationConfig.model_validate(LOBSTER), np.random.SeedSequence(1))


def test_gate_requires_commit_then_tag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "PREREGISTRATION.md").write_text("thesis\n")
    with pytest.raises(PreregistrationRequired, match="not committed"):
        require_preregistration()
    git(tmp_path, "add", "PREREGISTRATION.md")
    git(tmp_path, "commit", "-q", "-m", "prereg")
    with pytest.raises(PreregistrationRequired, match="no git tag"):
        require_preregistration()
    git(tmp_path, "tag", "prereg-v1")
    assert require_preregistration() == "prereg-v1"


def test_synthetic_runs_are_not_gated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = AblationConfig.model_validate(
        {
            "run_name": "x",
            "seed": 1,
            "data": {"source": "synthetic", "symbols": ["S"], "synthetic_duration_s": 60.0},
        }
    )
    assert load_sessions(cfg, np.random.SeedSequence(1))[0].symbol == "S"
