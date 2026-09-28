"""M4 holdout gate on a tiny synthetic fixture. Fixture output only."""

import json

import pytest

from asaudit.eval.holdout import HoldoutRefused, run_holdout

ABLATION = """
run_name = "tiny-holdout"
seed = 11
cancel_attribution = ["uniform"]
[data]
source = "synthetic"
symbols = ["SA"]
synthetic_duration_s = 300.0
episode_s = 30.0
calibration = 0.5
policy_fit = 0.3
holdout = 0.2
[strategies]
budget = 12
[eval]
bootstrap_repeats = 200
allow_unconverged = true
"""


def configs(tmp_path, authorized: bool):
    ab = tmp_path / "ab.toml"
    ab.write_text(ABLATION)
    hc = tmp_path / "holdout.toml"
    hc.write_text(
        f'ablation_config = "{ab}"\nholdout_authorized = {str(authorized).lower()}\n'
        f'ledger = "{tmp_path / "ledger.json"}"\nquote_sizes = [1, 10]\n'
    )
    return hc


def test_refused_without_both_authorizations(tmp_path):
    with pytest.raises(HoldoutRefused):
        run_holdout(configs(tmp_path, False), tmp_path / "out", True, cli_authorized=True)
    with pytest.raises(HoldoutRefused):
        run_holdout(configs(tmp_path, True), tmp_path / "out", True, cli_authorized=False)
    assert not (tmp_path / "ledger.json").exists()


def test_touched_once_then_refused_unless_reason_recorded(tmp_path):
    hc = configs(tmp_path, True)
    directory = run_holdout(hc, tmp_path / "out", True, cli_authorized=True)
    report = json.loads((directory / "holdout.json").read_text())
    assert report["fixture_output"] is True
    cell = report["results"]["size=1/uniform"]
    assert cell["n_episodes"] == 2
    assert set(cell) >= {"corrected:queue", "corrected:adverse", "corrected:both"}
    assert "size=10/uniform" in report["results"]
    with pytest.raises(HoldoutRefused):
        run_holdout(hc, tmp_path / "out", True, cli_authorized=True)
    run_holdout(hc, tmp_path / "out", True, cli_authorized=True, rerun_reason="test rerun")
    ledger = json.loads((tmp_path / "ledger.json").read_text())
    assert [e["rerun_reason"] for e in ledger] == [None, "test rerun"]
