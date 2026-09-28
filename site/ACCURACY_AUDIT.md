# Accuracy audit

Every public claim on the site, where it comes from, and what kind of evidence it is. The numbers in brackets are the page's source marks; each mark links to an entry in the page's Sources section, which links to the file. Paths are relative to the repository root.

**auto** marks a value rendered from `src/data/evidence.json` and enforced at build time. The build fails if the value in `index.html` differs from the evidence, or if its sentence has no source mark.

Evidence types: **Real** = market data. **Exact** = deterministic calculation, no data. **Synthetic** = generated order flow. **Illustration** = example quantities through a real rule. **Planned** = configuration, not yet run. **Record** = repository history or run log.

## Scope boundary (checked)

- No economic value from the synthetic run (shortfall, per-effect cost, train-test gap) appears on the page. Only pipeline facts do: symbol count, convergence count, budget, and the sign flip of the competition effect.
- The page never states or implies that queue position, adverse selection, competition or the corrected policy has been validated on real market data. The research-status block marks real-market attribution and the held-out result as pending.
- The capping rule is presented as inferred from the evidence, not as the authors' documented procedure.
- The 21 s replay time appears only with the label "Estimated, not measured".

## Hero

| Claim | Value | Source | Type |
|---|---|---|---|
| Stocks checked | 5 (auto) [1] | Five manifests in `docs/evidence/m0-normalization/`, status `passed` | Real, ingestion only |
| Exchange messages checked | 2,110,860 (auto) [1] | Sum of `n_events` in those manifests, commit `5b7cd8c` | Real, ingestion only |
| AS is a 2008 model | none | Avellaneda and Stoikov, Quantitative Finance 8(3), 2008 [2] | Literature |
| Primer (market maker, queue, fill assumption) | none | `PRD_as_audit.md` section 1 (A1) | Design, plain restatement |

## 01-03: explainers and question

| Claim | Source | Type |
|---|---|---|
| FIFO consumption; 24/30/10/12/8 example quantities | `src/asaudit/sim/fills/queue.py`; quantities chosen for the explainer | Illustration |
| Three cancellation policies; uniform readout is the expected value | `PRD_as_audit.md` section 4.3; the simulator draws a binomial | Rule |
| No finding reported when direction flips between extremes | `attribution/run.py` `_bounds` (`headline_reportable`) | Code |
| A1/A2/A3 definitions, hypothesis, success and failure criteria | `PRD_as_audit.md` sections 1, 1.1, 1.2, 3 | Design |
| Replication test committed before computing [5] | Commit `6adb9a3`; `docs/DECISIONS.md` | Record |
| Pre-registration drafted, not in force | `docs/PREREGISTRATION.draft.md`; code gate `require_preregistration` | Record |
| Paper settings: mid 100, σ 2, k 1.5, A 140, dt 0.005; γ 0.01, 0.1, 1 [2] | `tests/golden/as2008_table_qf2008.json` | Paper |
| 1,000 paths of 200 steps [2] | Same file: `n_simulations`, `T` / `dt` | Paper |
| Strict-rule failures in Tables 1 and 3 (auto) [3] | `docs/evidence/m1-qf2008/run/comparison.json` | Record |
| Raw fill chance up to 7.59 (auto) [3] | Same file, Table 3 `max_raw_probability` | Record |
| Quote explorer outputs | Computed live from the published equations and settings | Illustration of real formulas |

## 04: experiment

| Claim | Source | Type |
|---|---|---|
| Step statuses | `STATE.md` | Record |
| Steps are milestones M0 to M5 | `PRD_as_audit.md` section 6 | Design |
| Eight worlds, exact Shapley split | `attribution/grid.py`, `attribution/shapley.py` | Code |
| 000 reduces to the paper's model [6] | `tests/integration/test_grid_reduces_to_as.py` | Test |
| 40/30/30 split, 300 s episodes, 31/23/24 episodes, 09:30-16:00 [11] | `configs/ablation/lobster.toml`; `split_episodes` rounding over 78 episodes | Planned |
| Held-back data never replayed, access recorded | `tests/integration/test_ablation_pipeline.py`, `tests/integration/test_holdout_gate.py` | Test |
| Checks pass on GitHub | See "Continuous integration" below | Record |

## 05: research status and findings

| Claim | Value | Source | Type |
|---|---|---|---|
| Replication complete | none | [4] | Exact |
| Simulator validated | none | [6]: reduction test plus property tests on synthetic flow | Test |
| Pipeline validated on synthetic data only | none | [8] | Synthetic |
| Corrected policy reduces to AS with corrections off | none | [7] `tests/unit/test_corrected.py`; derivation section 2 | Test and derivation |
| Real-market attribution and held-out result pending | none | `STATE.md` | Record |
| Printed values tested | 27 (auto) [4] | `sensitivity.json`, `tests_run`, capped, dt 0.005 | Exact |
| Largest capped gap | 1.88 (auto) [4] | `max_abs_z` | Exact |
| Cut-off fixed in advance | 3.11 (auto) [4][5] | `threshold_abs_z`; declared in commit `6adb9a3` | Exact |
| Random-arrival rule failures | 7 of 27 (auto) [4] | `failures`, rule `poisson` | Exact |
| Worst random-arrival gap | 38.5 (auto) [4] | `max_abs_z` | Exact |
| Profit lower by about 12% in Table 1 | 12 (auto) [4] | Inventory `profit_mean` population, 57.17 vs 64.89 | Exact |
| dt 0.0025 and dt 0.001 failures | 6 and 11 (auto) [4] | `failures` | Exact |
| Paper sample size | 1,000 (auto) [2] | Golden `n_simulations` | Paper |
| Chart marks and table | every value [4] | `runs[].tests[]` | Exact |
| Clean commit of the study | e77692c (auto) [4] | Manifest `git_sha`, `git_dirty: false` | Record |
| 4 configurations, 1,500 paths, 4.5 standard errors [6] | none | `test_grid_reduces_to_as.py`: parametrisation, `N_PATHS`, tolerance | Test |
| Adverse-term sign opposite to the spec's sketch [7] | none | `docs/DERIVATION_M4.draft.md` section 3 vs `PRD_as_audit.md` M4 | Derivation |

## 06: what failed

| Claim | Value | Source | Type |
|---|---|---|---|
| Cases above 100% in the Table 3 run | 10,259 (auto) [3] | `comparison.json` `probability_exceedances` | Record |
| Original result still "not reproduced" [3] | none | `comparison.json` `accepted: false` | Record |
| Spec required ±10% on the ratio | none | `PRD_as_audit.md` M1 acceptance | Spec |
| Table 1 ratio: printed 3.70, exact 4.23, 14.2% apart, 1.64 standard errors | auto [4] | `sensitivity.json` Table 1 `variance_ratio` | Exact |
| Ratio sampling error about 8% | 8 (auto) [4] | Same, `se_log` = 0.081 | Exact |
| 5 synthetic stocks, 0 of 560 fits converged, budget 30 | auto [8] | `pco_folds.json`; manifest `config.strategies.budget` | Synthetic |
| Competition effect flipped direction | none [8] | `attribution.json` `bounds.A3.sign_flips_across_bounds` | Synthetic |
| Data host unreachable [15] | none | `docs/DECISIONS.md` "M2 implementation decisions" | Record |

## 07-09: engineering, correctness, bugs

| Claim | Source |
|---|---|
| 100 ms batches, six steps [12] | `sim/engine.py` docstring; `batch_ms = 100` in the ablation configs |
| Fill mechanics and modelling decisions [12] | `sim/fills/queue.py`, `sim/flow/*`, `sim/competition/elasticity.py`, `docs/DECISIONS.md` |
| Non-converging fits raise | `calibration/glm.py`; `allow_unconverged = false` in `configs/ablation/lobster.toml` |
| Manifests; uncommitted code refused | `logging.py` `RunManifest` |
| 146 passing tests (auto) [9] | `STATE.md` gate line; full local run of `pytest -q` in this pass |
| Test groups and what they catch | `tests/test_exact_moments.py`, `tests/test_m1_sensitivity.py`, `tests/property/`, `tests/golden/`, `tests/integration/`, `tests/unit/test_corrected.py` |
| Fresh run reproduced the committed synthetic run byte for byte [14] | See "Reproduce commands" |
| Bug 1: seeding; the old code fails the regression test [13] | `attribution/run.py` `child()`; `tests/integration/test_common_random_numbers.py`, checked against the old `spawn()` derivation |
| Bug 2: symbol collision, run discarded [13] | `docs/DECISIONS.md` "Invalidated fixture run"; `test_ablation_pipeline.py::test_each_symbol_is_attributed_separately` |

## Continuous integration

| Claim on page | Evidence |
|---|---|
| "All 8 runs up to commit `473fedd` passed" [9] | GitHub Actions workflow `verify` (`.github/workflows/ci.yml`: ruff, format, mypy --strict, pytest on Python 3.12), runs 1-8 on branch `claude/vibrant-pasteur-ppo9f4`, all `conclusion: success`, read through the GitHub API on 2026-09-28. The `site` workflow (release build with the Pages URL) succeeded at `ebc0930` and `473fedd`. |
| Nightly workflow | Not claimed on the page. Dispatched manually once at `473fedd`; see "Nightly run" below. |

Runs for commits after `473fedd` are not claimed on the page.

## 10: evidence boundary

Every row carries its own source mark, except rows whose basis is the absence of a run: the authors' procedure, the corrected rule, the container and the crypto capture. Those rows cite `STATE.md` here.

## 11: reproduce commands

| Command | Evidence it works |
|---|---|
| `uv sync --locked` and `uv run pytest -q` | 146 passed, local, this pass; `verify` workflow green on GitHub |
| `uv run asaudit m1-sensitivity`, about 5 minutes | Evidence run manifest: 317 s (auto) [4] |
| `uv run asaudit replicate …`, exits 1 | Run inside `reproduce` from a clean worktree at `64180d8`; `accepted=False` |
| `uv run asaudit reproduce --paper --fixture --workers 4` | Run end to end from a clean worktree at `64180d8`, exit 0, 24 min on 4 cores. `episodes.parquet` and `pco_folds.json` byte-identical to `docs/evidence/m3-fixture/run` [14] |
| LOBSTER reproduction | Not run. Labelled "Not yet run". Now refused in code until `PREREGISTRATION.md` is committed and tagged |
| `uv run asaudit benchmark …` | Run with this exact command line from the clean worktree at `64180d8`, manifest `status: completed` |

## Container run

- Image `as-audit:local` (`sha256:b8d71a9c…`, 534 MB) built from the clean commit `473fedd`: `python:3.12.7-bookworm`, uv 0.8.22 from PyPI, `uv sync --locked`. Inside the image `git status --porcelain` is empty, so provenance checks pass.
- `docker run --network none … uv run --frozen pytest -q`: **146 passed**.
- `docker run --network none as-audit:local reproduce --paper --fixture --workers 4`: **exit 0**, 24 min 20 s. The original seeded comparison, moments, sensitivity and synthetic attribution all completed.
- Not checked: byte-identity of the container's outputs. That run wrote its results inside the container, which was discarded. Byte-identity was checked for the same command run natively (see above).
- Build requirement in restricted networks: pass `--network host` and proxy build args. `ghcr.io` and plain-HTTP Debian mirrors are not needed by the Dockerfile.

## Nightly run

Not claimed on the page. Run 36478047488 (manual dispatch at `473fedd`, GitHub-hosted `ubuntu-latest`), conclusion **failure**:

| Step | Outcome |
|---|---|
| Tests (`pytest -q`) | success |
| Full reproduction on synthetic order flow | success (37.9 min) |
| LOBSTER sample download (checksums verified) | success |
| Market-data validation | **failure**. AAPL passed (400,391 rows, matching the committed M0 manifest). AMZN failed at event 29331 on a sub-nanosecond timestamp (`36754.716797047004`) under the strict default timestamp policy. |
| Full reproduction on market data | skipped: no `PREREGISTRATION.md` (as designed) |

Root cause: the workflow omitted `--config configs/data/lobster.toml`, which selects the `nearest_ns` timestamp policy documented in `docs/reports/M0.md`. The data and code are unchanged. The workflow is fixed, and the outcome of the re-run is recorded below when available.
