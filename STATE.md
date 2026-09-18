# as-audit state
Updated: 2026-09-18T23:46:34.879412+00:00
Milestone: M0, in progress

## Acceptance criteria
- [x] Typed scaffold, pinned dependencies, CI configuration and local tests.
- [x] AAPL validation command exits 0; GOOG also passes.
- [ ] All five samples pass: AMZN, INTC and MSFT reject non-integral nanosecond timestamps.
- [ ] Live one-hour collector acceptance: not run; local disconnect fixture passes.

## Gate status
ruff: pass; format: pass; mypy: pass; pytest: 32 passed, 0 failed.
Remote CI: not run.

## Open blockers
Timestamp policy; live collector evidence. M1 also awaits the human-owned golden table and derivation.

## Awaiting user decision
Approve explicit nearest-nanosecond normalization with source provenance, or provide corrected inputs.

## Self-audit findings outstanding
BLOCKER: Ten source timestamps cannot be represented exactly as integer nanoseconds.
SUSPECT: Bounded snapshots lack full queue identity; reconnect snapshots do not recover missed events.

## Next session should
Resolve timestamp policy, rerun failed samples, and review collector evidence. Remain in M0.

## Last commit message
Record M0 verification and timestamp policy blocker
