# as-audit

M0 is blocked on the reconstruction contract. No simulator or research result exists yet.
This checkpoint contains the original specification, approved decisions, a source-feasibility diagnostic, and measured evidence of a data boundary limitation.

## Reproduce the source diagnostic

With Python 3.11 or newer, run:

```bash
python scripts/audit_sample_boundaries.py /tmp/as-audit-samples
```

The script downloads five official level-10 sample archives into the selected cache, validates paired row counts and column counts, computes archive checksums, and locates the first positive-size level whose price is absent from every preceding supplied snapshot and every message up through the current event. It emits descriptive source-audit metadata, not strategy performance or statistical estimates. Compare the output with `docs/evidence/source_audit.json`.

A boundary witness establishes missing information for reconstruction from messages plus an initial bounded snapshot. It does not prove that full-depth ITCH reconstruction is impossible. Source snapshots cannot both supply a boundary level and independently validate that same level.

Raw data, virtual environments, account information, and the career profile are excluded from this checkpoint. The user-owned derivation, preregistration, and golden table have not been created or changed.

Read `STATE.md` and `docs/DECISIONS.md` before resuming.
