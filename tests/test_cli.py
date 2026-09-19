import json
from pathlib import Path

from typer.testing import CliRunner

from asaudit.cli import app


def test_missing_data_exits_nonzero_and_writes_failure_manifest(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "data",
            "validate",
            "--source",
            "lobster",
            "--symbol",
            "AAPL",
            "--date",
            "2012-06-21",
            "--data-root",
            str(tmp_path / "absent"),
            "--output",
            str(tmp_path / "out"),
            "--allow-dirty",
        ],
    )
    assert result.exit_code != 0
    manifest = json.loads(next((tmp_path / "out").glob("*/manifest.json")).read_text())
    assert manifest["status"] == "failed"
    assert "traceback" in manifest


def test_approved_policy_and_adjustment_are_written_to_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "AAPL_2012-06-21_test_message_1.csv").write_text(
        "36754.716797047004,5,1,1,10100,-1\n"
    )
    (source / "AAPL_2012-06-21_test_orderbook_1.csv").write_text("10100,10,10000,10\n")
    config = tmp_path / "config.toml"
    config.write_text('depth = 1\ntimestamp_policy = "nearest_ns"\n')
    result = CliRunner().invoke(
        app,
        [
            "data",
            "validate",
            "--data-root",
            str(source),
            "--output",
            str(tmp_path / "out"),
            "--config",
            str(config),
            "--allow-dirty",
        ],
    )
    assert result.exit_code == 0, result.output
    manifest = json.loads(next((tmp_path / "out").glob("*/manifest.json")).read_text())
    assert manifest["config"]["timestamp_policy"] == "nearest_ns"
    assert manifest["data_quality"]["normalized_timestamps"] == 1
    assert (
        manifest["data_quality"]["timestamp_adjustments"][0]["raw_seconds"] == "36754.716797047004"
    )
    assert manifest["data_quality"]["timestamp_adjustments"][0]["adjustment_ns"] == "-0.004"
