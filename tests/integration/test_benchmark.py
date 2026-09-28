import json

from asaudit.eval.benchmark import run_benchmark
from integration.test_holdout_gate import ABLATION


def test_example_submission_is_scored_beside_baselines(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path.parent)  # cwd without benchmarks/: import must still resolve
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    cfg = tmp_path / "ab.toml"
    cfg.write_text(ABLATION)
    directory = run_benchmark("benchmarks.example_quoter:make", cfg, tmp_path / "out", True)
    report = json.loads((directory / "benchmark.json").read_text())
    assert report["fixture_output"] is True
    cell = report["cells"]["111/uniform"]
    assert set(cell) == {"avellaneda_stoikov", "symmetric", "submission"}
    assert (
        cell["submission"]["ci"][0] <= cell["submission"]["mean_pnl"] <= cell["submission"]["ci"][1]
    )
