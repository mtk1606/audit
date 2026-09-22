# as-audit

A reproducible audit of the Avellaneda-Stoikov market-making model.

The project tests where a theoretical quoting model agrees with its source experiment,
and eventually how queue position, adverse selection and competing liquidity change
its performance. Every reported experiment retains its inputs, code revision and results.

## Current result

**The published 2008 benchmark is implemented; M1 verification remains incomplete.**
Table 2 passes the strict numerical comparison. Tables 1 and 3 agree with the
reference only under explicitly capped fill probabilities, a convention the paper
does not specify. These diagnostics do not count as primary acceptance.

Read the [published comparison](docs/reports/M1-qf2008.md) for results and confidence
intervals, the [earlier audit](docs/reports/M1.md) for the 2006 working paper, or the
[derivation](docs/DERIVATION.md) for the equations and assumptions.

## Reproduce

```bash
uv sync --locked
uv run asaudit replicate --config configs/replication/qf2008.toml --reference tests/golden/as2008_table_qf2008.json
```

Use Python 3.11+ and a clean Git checkout. The command currently exits 1 because
research acceptance fails. Its output directory contains the comparison, manifest and
path-level Parquet samples. An unsuccessful replication is retained as evidence.

Read the [independent mathematical verification](docs/reports/M1-moments.md) for the
model checks that do not depend on a Monte Carlo seed.

## Implementation

- Analytical AS quotes, symmetric benchmark and a deterministic Monte Carlo experiment.
- Independent random streams, bootstrap intervals and accounting checks at every step.
- Deterministic population moments verified against exhaustive paths and closed-form results.
- Five validated LOBSTER samples covering 2,110,860 events, with explicit supplied-boundary and timestamp provenance.
- Restartable L3 collection with sequence checks and atomic Parquet output.
- 72 passing tests, strict typing, linting and a pinned environment.

M0 is user-accepted; the live collector evidence remains outstanding. M1 is in progress.
No market backtest, strategy-performance claim or M2 ablation has been completed.

[Operations](docs/OPERATIONS.md) · [M0 evidence](docs/reports/M0.md) · [Decisions](docs/DECISIONS.md) · [State](STATE.md)
