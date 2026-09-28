# as-audit state
Updated: 2026-09-28T19:00:00+00:00
Milestone: M1 awaiting user confirmation (amended criterion); M2-M5 built ahead of the gate on user instruction; no market-data results exist

## Acceptance criteria
- [x] M0 user-accepted. Live collector evidence still outstanding.
- [x] M1 original contract: unchanged, still `not_reproduced` (Tables 1 and 3 strict: invalid probabilities).
- [x] M1 sensitivity study, pre-declared in DECISIONS (6adb9a3): capped law passes 27/27 tests (max |z| 1.88); Poisson rule fails 7/27; dt 0.0025 and 0.001 fail. `asaudit m1-sensitivity`.
- [ ] M1 amended criterion: **user decision** (docs/reports/M1-sensitivity.md, "Proposed amendment").
- [x] M2 (off, off, off) reduces to the exact M1 law; property tests (accounting, no through fills, queue monotone, reprice to back, inventory = sum of fills, bound ordering); golden fill hashes; 8 cells complete. All on **synthetic** L3.
- [ ] M2 on LOBSTER: blocked; php.lobsterdata.com is denied by this environment's network policy.
- [ ] M2 replay throughput measured on real data (projected about 21 s/session vs 30 s budget).
- [x] M3 machinery: exact Shapley (efficiency asserted), stationary bootstrap with Politis-White, regimes, walk-forward PCO (linear_skew, tabular_binned), bounds with sign-flip flags, A2 first. Fixture run only.
- [ ] M3 on market data: needs data, plus PREREGISTRATION.md committed and tagged by the owner (draft: docs/PREREGISTRATION.draft.md).
- [x] M4 corrected rule derived (docs/DERIVATION_M4.draft.md, owner review) and implemented; reduces to AS with both terms off; holdout gate with ledger.
- [ ] M4 held-out evaluation: not run (gated, requires M3 sign-off).
- [x] M5 `asaudit reproduce --paper [--fixture]`, `asaudit benchmark`, Dockerfile, nightly CI workflow.
- [x] M5 remote CI: verify workflow green on GitHub (8/8 runs through 473fedd).
- [x] M5 clean-container reproduction: image built at 473fedd, run with --network none: 146 tests pass, `reproduce --paper --fixture` exit 0 (24 min).

## Gate status
ruff: pass; format: pass; mypy --strict: pass (61 files); pytest: 146 passed, 0 failed.
Remote CI: the "verify" workflow (ruff, format, mypy, pytest on Python 3.12) passed on GitHub for all 8 pushes through 473fedd; the "site" release build passed at ebc0930 and 473fedd. Nightly: first manual run at 473fedd failed at market-data validation (workflow omitted --config configs/data/lobster.toml; AAPL passed, AMZN hit a sub-nanosecond timestamp under the strict policy). Tests, synthetic reproduction and LOBSTER download passed; market step skipped as designed. Workflow fixed; re-run 36483785115 at 107a46b succeeded: tests, synthetic reproduction, LOBSTER download (checksums verified) and validation of all five symbols (2,110,860 rows, 10 timestamp adjustments, matching M0 exactly); market step skipped as designed.

## Container
Image builds from python:3.12.7-bookworm with uv 0.8.22 from PyPI (ghcr.io and plain-HTTP Debian mirrors are unreachable from this environment). Run offline at 473fedd: 146 tests pass; synthetic reproduction exit 0. Output byte-identity inside the container not checked.

## Open blockers
- Market data access from this environment (LOBSTER host denied). Run locally, or allow the host in the environment's network settings.
- PREREGISTRATION.md must be owner-committed and tagged before any market M3 number. Enforced in code: load_sessions refuses LOBSTER data until PREREGISTRATION.md is committed and a git tag contains it (tests/test_preregistration_gate.py); the nightly market step is skipped until the file exists.

## Awaiting user decision
1. Adopt the amended M1 criterion and completion wording, or keep M1 in progress.
2. Review and commit PREREGISTRATION.md (from the draft), then tag it.
3. Review docs/DERIVATION_M4.draft.md; merge it into DERIVATION.md if accepted. Note the adverse-term sign differs from the PRD sketch.
4. Accept deviations: sep-CMA-ES instead of full CMA-ES; conditional-mean A2 charge; A3 acting only through cancels ahead.

## Self-audit findings outstanding
- SUSPECT: `pi(Q)` in the corrected rule is a within-horizon probability used as an intensity multiplier.
- SUSPECT: the A2 charge values fills at a fixed 1 s horizon, not holding-period exposure.
- SUSPECT: cross-machine byte identity of golden fills is unverified (libm differences in the generator are possible).
- NIT: `ReactiveAgents` (optional) not implemented. No Coinbase-to-ReplaySession adapter yet.
- Resolved this session: seeds must use explicit keys (SeedSequence.spawn mutates; regression test tests/integration/test_common_random_numbers.py); the synthetic symbol collision invalidated the first fixture run (discarded, recorded in DECISIONS).

## Next session should
Fetch the LOBSTER sample on a machine with network access and run
`asaudit data validate` for all five symbols. Then run the M2 grid on one real
session to measure throughput and confirm the property tests on real flow.
After the owner commits and tags PREREGISTRATION.md, run
`asaudit ablate --config configs/ablation/lobster.toml --workers 8`, report A2
first, and only then consider M4.
