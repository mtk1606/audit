"""End-to-end M3 pipeline on a tiny synthetic fixture (fixture output only)."""

import json

import polars as pl
import pytest

from asaudit.attribution.run import run_ablation

CONFIG = """
run_name = "tiny"
seed = 7
cancel_attribution = ["pessimistic", "uniform", "optimistic"]
[data]
source = "synthetic"
symbols = ["SA", "SB"]
synthetic_duration_s = 300.0
episode_s = 30.0
calibration = 0.5
policy_fit = 0.4
holdout = 0.1
[strategies]
budget = 12
[eval]
bootstrap_repeats = 200
min_train = 1
allow_unconverged = true
"""


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    root = tmp_path_factory.mktemp("abl")
    cfg = root / "tiny.toml"
    cfg.write_text(CONFIG)
    serial = run_ablation(cfg, root / "serial", allow_dirty=True, workers=1)
    parallel = run_ablation(cfg, root / "parallel", allow_dirty=True, workers=2)
    return serial, parallel


def test_outputs_and_labels(runs):
    (directory, report), _ = runs
    for name in (
        "manifest.json",
        "episodes.parquet",
        "attribution.json",
        "pco_folds.json",
        "attribution.png",
    ):
        assert (directory / name).exists()
    assert report["fixture_output"] is True and "FIXTURE" in report["label"]
    assert report["axes_order"][0] == "A2"  # PRD: adverse selection reported first
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["data_quality"]["holdout_episodes_not_replayed"] == 2
    assert manifest["status"] == "completed"


def test_each_symbol_is_attributed_separately(runs):
    (directory, report), _ = runs
    frame = pl.read_parquet(directory / "episodes.parquet")
    assert set(frame["symbol"].unique()) == {"SA", "SB"}
    per_symbol = report["strategies"]["avellaneda_stoikov"]["by_cancel_policy"]["uniform"]
    assert set(per_symbol["per_symbol"]) == {"SA", "SB"}
    assert per_symbol["n_episodes"] == 6  # 3 out-of-sample episodes per symbol


def test_shapley_sums_to_total_per_episode(runs):
    (_, report), _ = runs
    for strat in report["strategies"].values():
        for pol in strat["by_cancel_policy"].values():
            for e in pol["episodes"]:
                assert e["A1"] + e["A2"] + e["A3"] == pytest.approx(e["gap_111"] - e["gap_000"])


def test_holdout_never_replayed_and_pco_is_out_of_sample(runs):
    (directory, _), _ = runs
    frame = pl.read_parquet(directory / "episodes.parquet")
    # 10 episodes per symbol: 5 calibration, 4 policy_fit (indices 5-8), 1 holdout (9).
    assert set(frame["episode"].unique()) == {5, 6, 7, 8}
    pco = frame.filter(pl.col("strategy").str.starts_with("pco:"))
    assert set(pco["episode"].unique()) == {6, 7, 8} and set(pco["sample"]) == {"test"}


def test_worker_count_does_not_change_results(runs):
    (d1, r1), (d2, r2) = runs
    a = pl.read_parquet(d1 / "episodes.parquet").sort(
        ["symbol", "episode", "grid", "cancel_policy", "strategy"]
    )
    b = pl.read_parquet(d2 / "episodes.parquet").sort(
        ["symbol", "episode", "grid", "cancel_policy", "strategy"]
    )
    assert a.equals(b)
    assert r1["strategies"] == r2["strategies"]
