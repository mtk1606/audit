import json
from pathlib import Path

from typer.testing import CliRunner

from asaudit.cli import app


def test_reference_is_user_supplied_working_paper():
    source = json.loads(Path("tests/golden/as2008_table.json").read_text())
    assert source["source"]["verified_by_human"] is False
    assert source["tables"][0]["inventory"]["profit_mean"] == 62.94
    assert source["tables"][2]["symmetric"]["final_q_std"] == 9.06


def test_research_cli_preserves_failed_acceptance_and_provenance(tmp_path):
    config = tmp_path / "smoke.toml"
    config.write_text("seed = 20260922\nn_paths = 16\nbootstrap_repeats = 100\n")
    result = CliRunner().invoke(
        app,
        ["replicate", "--config", str(config), "--output", str(tmp_path / "runs"), "--allow-dirty"],
    )
    assert result.exit_code == 1
    runs = list((tmp_path / "runs").iterdir())
    assert len(runs) == 1
    manifest = json.loads((runs[0] / "manifest.json").read_text())
    report = json.loads((runs[0] / "comparison.json").read_text())
    assert manifest["status"] == "not_reproduced"
    assert manifest["seed"] == 20260922
    assert manifest["data_checksums"]
    assert report["accepted"] is False
    assert report["source_version"] == "2006-10-05 working paper"
    assert len(report["experiments"]) == 9
    assert report["acceptance_eligible"] is False

    repeat = CliRunner().invoke(
        app,
        [
            "replicate",
            "--config",
            str(config),
            "--output",
            str(tmp_path / "repeat"),
            "--allow-dirty",
        ],
    )
    assert repeat.exit_code == 1
    repeated_run = next((tmp_path / "repeat").iterdir())
    assert (runs[0] / "comparison.json").read_bytes() == (
        repeated_run / "comparison.json"
    ).read_bytes()
    for path in runs[0].glob("*.parquet"):
        assert path.read_bytes() == (repeated_run / path.name).read_bytes()
