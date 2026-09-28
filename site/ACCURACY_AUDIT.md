# Accuracy audit

Every public claim on the site, where it comes from, and what kind of evidence it is. Paths are relative to the repository root. Values marked **auto** are rendered from `src/data/evidence.json` and checked against the static HTML by `scripts/check-claims.mjs` on every build.

Evidence types: **Real** = market data. **Exact** = deterministic computation, no data. **Synthetic** = generated order flow. **Illustration** = example quantities through a real rule. **Planned** = configuration, not yet run.

## Hero and metadata

| Claim | Value | Source | Type |
|---|---|---|---|
| LOBSTER samples validated | 5 (auto) | `docs/evidence/m0-normalization/*-manifest.json` (status `passed`), `docs/reports/M0.md` | Real, ingestion only |
| Events validated | 2,110,860 (auto) | Sum of `n_events` in the five M0 manifests, commit `5b7cd8c` | Real, ingestion only |
| Python 3.11+, strict typing, NumPy, Polars | none | `pyproject.toml` (`requires-python`, dependencies, `[tool.mypy] strict`) | Code |
| "Replication and simulator verified; market attribution remains" | none | `STATE.md` acceptance criteria | Status |

## 01 Queue explainer

| Claim | Source | Type |
|---|---|---|
| FIFO consumption, executions fill the queue ahead first | `src/asaudit/sim/fills/queue.py` | Rule |
| 24 ahead, sell order 30, your order 10, 12 behind, 8 cancelled | Example quantities chosen for the explainer | Illustration |
| Pessimistic / uniform / optimistic cancellation policies | `PRD_as_audit.md` section 4.3, `QueueFillModel` | Rule; the uniform readout shows the expectation, where the simulator draws a binomial |
| No headline when a conclusion flips sign between bounds | `attribution/run.py` `_bounds` (`headline_reportable`) | Code |

## 02 Question

| Claim | Source | Type |
|---|---|---|
| A1/A2/A3 definitions | `PRD_as_audit.md` section 1 | Design |
| Hypothesis, success and failure criteria, equal-prominence negative result | `PRD_as_audit.md` sections 1.1, 1.2, 3 | Design |
| Replication test fixed before computing, commit `6adb9a3` | `git log`; `docs/DECISIONS.md` "M1 bounded sensitivity protocol" | Process |
| Pre-registration drafted, not in force | `docs/PREREGISTRATION.draft.md` | Status |

## 03 The model

| Claim | Value | Source | Type |
|---|---|---|---|
| Parameters | mid 100, σ 2, k 1.5, A 140, dt 0.005 | `tests/golden/as2008_table_qf2008.json` `simulation_params` (read into evidence.json) | Paper |
| γ values | 0.1, 0.01, 1 (Tables 1-3) | same file, `tables[].gamma` | Paper |
| Equations | r, spread, λ(δ) | same file, `formulas_as_printed`; `strategy/avellaneda_stoikov.py` | Paper |
| 1,000 paths, 200 steps | n = 1000, T/dt = 200 | golden file `n_simulations`, `T`, `dt` | Paper |
| Tables with invalid strict probabilities | 1 and 3 (auto) | `docs/evidence/m1-qf2008/run/comparison.json` (`published_strict`, status `invalid_probability`) | Exact run record |
| Largest raw probability | 7.59 (auto) | same file, Table 3 `published_saturated` `max_raw_probability` | Seeded run |
| Explorer outputs | computed live | `src/figures/quotes.ts` uses the equations above with the paper parameters | Illustration of real formulas |

## 04 Experiment

| Claim | Source | Type |
|---|---|---|
| Stage statuses M0-M5 | `STATE.md` | Status |
| 8 configurations, exact Shapley | `attribution/grid.py`, `attribution/shapley.py` | Code |
| 000 reduces to M1 | `tests/integration/test_grid_reduces_to_as.py` | Test |
| Split 40/30/30, 300 s episodes, 31/23/24 episodes, 09:30-16:00 | `configs/ablation/lobster.toml`; rounding in `attribution/run.py` `split_episodes` (78 episodes) | Planned |
| Holdout never replayed; access recorded | `tests/integration/test_ablation_pipeline.py`, `tests/integration/test_holdout_gate.py`, `eval/holdout.py` | Test |

## 05 What I found

All M1 values: `docs/evidence/m1-sensitivity/run/sensitivity.json`, clean commit `e77692c`, via evidence.json. Type: **Exact**. No market data.

| Claim | Value | Field |
|---|---|---|
| Printed values tested | 27 (auto) | `tests_run` for rule `saturate`, dt 0.005 |
| Largest capped deviation | 1.88 (auto) | `max_abs_z` |
| Threshold | 3.11 (auto) | `threshold_abs_z` (Bonferroni, 27 tests, two-sided 5%) |
| Poisson rule failures | 7 of 27 (auto) | `failures` for `poisson`, dt 0.005 |
| Worst Poisson deviation | 38.5 (auto) | `max_abs_z` |
| Poisson lowers Table 1 expected profit | about 12% (auto) | inventory `profit_mean` population, 57.17 vs 64.89 |
| dt 0.0025 failures | 6 (auto) | `failures`, `saturate`, dt 0.0025 |
| dt 0.001 failures | 11 (auto) | `failures`, `saturate`, dt 0.001 |
| Paper sample size | 1,000 (auto) | golden `n_simulations` |
| z-chart marks and table | every value | `runs[].tests[]` |
| Capping is inferred, not documented | none | The paper is silent: `tests/golden/as2008_table_qf2008.json` `transcription_notes`, `docs/reports/M1-qf2008.md` |
| Simulator reduction: 4 configurations, 1,500 paths, 4.5 SE | none | `tests/integration/test_grid_reduces_to_as.py` (`N_PATHS`, tolerance, parametrisation) |
| Corrected rule reduces to AS | none | `tests/unit/test_corrected.py` |
| Adverse term sign opposite to the spec sketch | none | `docs/DERIVATION_M4.draft.md` section 3; `PRD_as_audit.md` M4 |
| Corrected rule not evaluated on market data | none | `STATE.md` |

## 06 What failed

| Claim | Value | Source | Type |
|---|---|---|---|
| Table 3 cases above one | 10,259 (auto) | `comparison.json` Table 3 `probability_exceedances` | Seeded run |
| Original contract still "not reproduced" | none | `comparison.json` `accepted: false`; `docs/reports/M1-qf2008.md` | Record |
| 10% ratio criterion | none | `PRD_as_audit.md` M1 acceptance | Spec |
| Table 1 ratio: printed 3.70, exact 4.23, 14.2%, 1.64 SE | auto | `sensitivity.json` Table 1 `variance_ratio` | Exact |
| Ratio sampling error about 8% | 0.081 | same, `se_log` for Table 1 | Exact |
| Fixture: 5 symbols, 0 of 560 converged, budget 30 | auto | `docs/evidence/m3-fixture/run/pco_folds.json`, `manifest.json` `config.strategies.budget` | Synthetic |
| Competition sign flip across bounds | none | `attribution.json` `bounds.A3.sign_flips_across_bounds` | Synthetic |
| Economic fixture values are not shown | none | By design; the page contains none | Policy |
| Data host unreachable | none | `docs/DECISIONS.md` "M2 implementation decisions" | Record |

## 07-09 Engineering, correctness, bugs

| Claim | Source |
|---|---|
| 100 ms batches, six-step loop | `sim/engine.py` docstring; `batch_ms = 100` in `configs/ablation/*.toml` |
| Fill mechanics list | `sim/fills/queue.py` docstring and code; `tests/property/test_engine_properties.py` |
| A2 as target minus embedded, A3 via cancels | `sim/flow/*`, `sim/competition/elasticity.py`, `docs/DECISIONS.md` |
| Integer ticks and nanoseconds | `types.py`, `sim/session.py` |
| Non-converged fits raise | `calibration/glm.py`; PCO: `allow_unconverged = false` in `configs/ablation/lobster.toml` |
| Manifests, dirty-tree refusal | `logging.py` `RunManifest` |
| 143 passing tests (auto) | `STATE.md` gate line; full `pytest -q` run at commit `64180d8` |
| Moment recurrence vs exhaustive paths | `tests/test_exact_moments.py`, `tests/test_m1_sensitivity.py` |
| Property tests | `tests/property/test_engine_properties.py` |
| Golden fill hashes | `tests/golden/test_fill_golden.py`, `tests/golden/fills_fixture.json` |
| Common random numbers | `tests/integration/test_common_random_numbers.py` (fails under the old `spawn()` derivation) |
| Worker-count invariance, Shapley efficiency, symbol separation, holdout never replayed | `tests/integration/test_ablation_pipeline.py` |
| Holdout ledger | `tests/integration/test_holdout_gate.py` |
| Fresh run reproduced the committed fixture byte for byte | `reproduce --paper --fixture` from a clean worktree at `64180d8`: `episodes.parquet` and `pco_folds.json` SHA-256 identical to `docs/evidence/m3-fixture/run` (run at `256b7c8`); `attribution.json` strategies equal |
| Nightly CI configured, not run | `.github/workflows/nightly.yml`; `STATE.md` "Remote CI: not run" |
| Bug 1, seeding | `attribution/run.py` `child()` docstring; `STATE.md` self-audit |
| Bug 2, symbol collision; run discarded | `docs/DECISIONS.md` "Invalidated fixture run" |

## 10 Evidence boundary

| Row | Status | Source |
|---|---|---|
| LOBSTER message-by-message validation | Verified | `docs/reports/M0.md` (snapshot-assisted; supplied boundary levels are labelled) |
| Tables consistent with capped fills | Verified | M1 sensitivity evidence |
| Authors used capped fills | Supported, not confirmed | The paper is silent |
| Simulator reduces to paper model | Verified | Integration test |
| Invariants on order-book flow | Synthetic only | Property tests run on synthetic sessions |
| About 21 s per trading day | Estimated, not measured | `docs/reports/M2.md`, projection from a 3.6 s synthetic run |
| A1/A2/A3 costs | Real-data test pending | `STATE.md` |
| Corrected rule | Not evaluated | `STATE.md` |
| One-command reproduction | Partially verified | Local fixture run (see below); remote CI not run |
| Live crypto capture | Pending | `STATE.md`, M0 |

## 11 Reproduce commands

| Command | Evidence it works |
|---|---|
| `uv sync --locked`, `uv run pytest -q` | 143 passed at `64180d8` |
| `uv run asaudit m1-sensitivity` (about 5 minutes) | Evidence run: 317 s elapsed (`docs/evidence/m1-sensitivity/run/manifest.json`) |
| `uv run asaudit replicate --config configs/replication/qf2008.toml --reference tests/golden/as2008_table_qf2008.json`, exits 1 | Run inside `reproduce` from a clean worktree at `64180d8`; `accepted=False` |
| `uv run asaudit reproduce --paper --fixture --workers 4` | Run end to end from a clean worktree at `64180d8`, exit 0 (this audit's session) |
| `uv run asaudit reproduce --paper --workers 8` (LOBSTER) | **Not run.** Labelled "Not yet run" |
| `uv run asaudit benchmark --quoter benchmarks.example_quoter:make --config configs/ablation/fixture.toml` | Run with this exact command line (this audit's session), exit 0 |

## Deliberately absent

- No M3 economic value (shortfall, per-axis bps, train-test gap) from the synthetic fixture appears anywhere.
- No claim that the authors used capping, that the simulator is validated on market data, that the corrected rule works, or that remote CI has passed.
- The 21 s replay figure appears only with its "estimated, not measured" label.
- The Dockerfile exists but has never been built: no Docker daemon was available. The site says only that Docker support was built, never that it was run.
