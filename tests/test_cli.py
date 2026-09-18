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
