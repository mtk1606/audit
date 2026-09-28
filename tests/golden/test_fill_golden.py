"""Fixed seed + fixed config => byte-identical fill sequence (PRD M2).

The expected hashes in fills_fixture.json are agent-generated regression
fixtures on synthetic data, not source-paper values. Regenerate only for an
intentional, documented change of simulator semantics:
    PYTHONPATH=tests uv run python tests/golden/test_fill_golden.py --write
"""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from fixtures import calibration, session

from asaudit.attribution.grid import ALL_CONFIGS, build_models
from asaudit.sim.engine import Engine, EngineConfig, ReplaySource
from asaudit.strategy.avellaneda_stoikov import ASQuoter

GOLDEN = Path(__file__).with_name("fills_fixture.json")


def fill_digests() -> dict[str, str]:
    s, cal = session(10, 60.0), calibration()
    out: dict[str, str] = {}
    for g in ALL_CONFIGS:
        for policy in ("pessimistic", "uniform", "optimistic"):
            fill, info, comp = build_models(g, cal, policy)
            engine = Engine(EngineConfig(latency_ns=100_000, max_inventory=15), fill, info, comp)
            quoter = ASQuoter(1e-4, cal.sigma, cal.intensity.k, 60.0, s.tick)
            r = engine.run(
                ReplaySource(s, 100_000_000, s.start_ns, s.end_ns),
                quoter,
                np.random.default_rng(20260913),
                s.session_id,
            )
            rows = [
                [
                    f.ts_ns,
                    int(f.side),
                    f.price_ticks,
                    f.size,
                    f.queue_pos_at_entry,
                    f.queue_pos_at_fill,
                    repr(f.mid_at_fill),
                ]
                for f in r.fills
            ]
            payload = json.dumps({"fills": rows, "pnl": repr(r.pnl)}, separators=(",", ":"))
            out[f"{g.label}/{policy}"] = hashlib.sha256(payload.encode()).hexdigest()
    return out


def test_fill_sequences_are_byte_identical_to_golden():
    assert fill_digests() == json.loads(GOLDEN.read_text())


def test_rerun_is_identical():
    assert fill_digests() == fill_digests()


if __name__ == "__main__" and "--write" in sys.argv:
    GOLDEN.write_text(json.dumps(fill_digests(), indent=2, sort_keys=True) + "\n")
