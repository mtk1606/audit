import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from asaudit.eval.replication import Reference
from asaudit.sim.replication import SimulationConfig, simulate
from asaudit.strategy.avellaneda_stoikov import ASParameters
from asaudit.strategy.symmetric import average_spread_quote


def test_published_average_spread_not_instantaneous_or_liquidity_only():
    p = ASParameters(gamma=0.1, sigma=2, k=1.5)
    result = average_spread_quote(100, p)
    assert result.spread == pytest.approx(1.4907704227514234)
    assert result.reservation == 100
    assert round(average_spread_quote(100, ASParameters(gamma=1)).spread, 2) == 3.02


def test_source_versions_preserve_original_values():
    published = Reference.model_validate_json(
        Path("tests/golden/as2008_table_qf2008.json").read_text()
    )
    old = Reference.model_validate_json(Path("tests/golden/as2008_table.json").read_text())
    assert published.tables[2].gamma == 1
    assert old.tables[2].gamma == 0.5
    assert published.tables[0].inventory.spread == 1.49
    assert published.tables[0].symmetric.profit_std == 12.7


def test_empty_or_duplicate_tables_cannot_vacuously_pass():
    data = json.loads(Path("tests/golden/as2008_table_qf2008.json").read_text())
    data["tables"] = []
    with pytest.raises(ValidationError):
        Reference.model_validate(data)
    data = json.loads(Path("tests/golden/as2008_table_qf2008.json").read_text())
    data["tables"][2] = data["tables"][0]
    with pytest.raises(ValidationError):
        Reference.model_validate(data)


def test_average_benchmark_has_constant_known_probability():
    cfg = SimulationConfig(symmetric=True, spread="average", n_paths=20)
    result = simulate(cfg, np.random.SeedSequence(123))
    expected = (
        cfg.A * np.exp(-cfg.k * average_spread_quote(100, ASParameters()).spread / 2) * cfg.dt
    )
    assert result.max_probability == pytest.approx(expected)
    assert result.probability_exceedances == 0


def test_published_runner_uses_average_spread_and_preserves_failure(tmp_path):
    from asaudit.eval.replication import run_replication

    config = tmp_path / "plan.toml"
    config.write_text("seed = 20260922\nn_paths = 32\nbootstrap_repeats = 100\n")
    directory, accepted = run_replication(
        config, Path("tests/golden/as2008_table_qf2008.json"), tmp_path / "runs", True
    )
    assert not accepted
    report = json.loads((directory / "comparison.json").read_text())
    manifest = json.loads((directory / "manifest.json").read_text())
    assert len(report["experiments"]) == 6
    assert report["source_version"] == "QF 2008 published article"
    for stream in manifest["streams"]:
        assert stream["simulation_spawn_key"][0] == 2008
        assert stream["config"]["spread"] == (
            "average" if stream["config"]["symmetric"] else "equation"
        )
    assert report["experiments"][4]["gamma"] == 1
