# as-audit state
Updated: 2026-09-22T01:30:16.089993+00:00
Milestone: M1, in progress

## Acceptance criteria
- [x] M0 user-accepted; live collector evidence still outstanding.
- [x] Both source tables retained unchanged and agent-checked against the supplied PDFs.
- [x] Published 2008 source identified; average-spread benchmark and gamma=1 Table 3 implemented.
- [x] Derivation, accounting checks, deterministic experiments and bootstrap intervals.
- [x] Published Table 2 strict comparison passes all numerical criteria.
- [ ] Published Tables 1 and 3 strict acceptance: invalid Bernoulli probabilities.
- [ ] Overall M1 acceptance: incomplete. Capped cases are diagnostics only.

## Gate status
ruff: pass; format: pass; mypy: pass, 28 source files; pytest: 66 passed, 0 failed.
Published research command: exit 1, status not_reproduced. Remote CI: not run.

## Open blockers
Probability-overflow convention is unspecified by the published paper.
Tables 1 and 3 match numerically under explicit capping, but strict runs fail.
The separate capped Table 2 realization misses the 10% variance-ratio tolerance.

## Awaiting user decision
None for implementation authority. Do not mix passing cases across independent variants.

## Self-audit findings outstanding
BLOCKER: primary replication incomplete. SUSPECT: unspecified overflow and side dependence.
SUSPECT: pointwise Monte Carlo acceptance can reject some correct realizations; no seed search.
M0 limitations remain: bounded queue identity and absent live collector acceptance evidence.

## Next session should
Seek original code or author clarification for the probability and update conventions.
Preserve both source versions and all fixed-seed outcomes. Report qualified numerical
agreement separately from faithful source-procedure verification. Remain in M1.
