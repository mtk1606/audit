# as-audit state
Updated: 2026-09-22T00:12:11.655381+00:00
Milestone: M1, in progress

## Acceptance criteria
- [x] M0 accepted by user; live collector evidence remains outstanding.
- [x] User-supplied golden table retained unchanged and visually checked against the supplied 2006 PDF.
- [x] HJB and frozen-inventory derivation written, algebra reviewed, tested and committed.
- [x] Analytical AS and symmetric quotes; source-specific Monte Carlo harness with manifests.
- [x] Deterministic path outputs, accounting checks, bootstrap intervals and explicit diagnostics.
- [ ] Primary means and standard deviations within source-target confidence intervals: not reproduced.
- [ ] Primary variance-ratio acceptance: unresolved because two inventory runs have invalid probabilities.
- [ ] Published 2008 replication: supplied source is the 2006 working paper.

## Gate status
ruff: pass; format: pass; mypy: pass, 28 source files; pytest: 61 passed, 0 failed.
Research command: exit 1, status not_reproduced. Remote CI: not run.

## Open blockers
Source interpretation and primary numerical replication. Full evidence in docs/reports/M1.md.

## Awaiting user decision
None for implementation authority. User explicitly authorized authorship and remaining decisions.
Do not equate this authority with successful empirical acceptance.

## Self-audit findings outstanding
BLOCKER: M1 replication criteria fail under the recorded protocol.
SUSPECT: source spread conventions and invalid Bernoulli probabilities; capped cases are diagnostics only.
SUSPECT: M0 bounded snapshots lack queue identity; live collector evidence is absent.

## Next session should
Resolve the numerical source ambiguities using stronger source evidence. Preserve the current
fixed-seed results and implement any new interpretation as a separate documented experiment.
Remain in M1; do not claim a published-version replication or begin M2 on these results.
