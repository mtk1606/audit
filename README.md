# as-audit

A reproducible audit of the Avellaneda-Stoikov market-making model.

The project tests where a theoretical quoting model agrees with its source experiment,
and eventually how queue position, adverse selection and competing liquidity change
its performance. Every reported experiment retains its inputs, code revision and results.

## Current result

**The supplied 2006 working-paper tables are not reproduced under the declared protocol.**
The implementation exposes invalid Bernoulli probabilities and differences between the
paper's quoted formula and table spreads. Diagnostic alternatives remain separate from
primary acceptance. This is not yet a verified replication of the 2008 publication.

Read the [M1 audit](docs/reports/M1.md) for comparisons and confidence intervals, or the
[derivation](docs/DERIVATION.md) for the model and its assumptions.

## Reproduce

```bash
uv sync --locked
uv run asaudit replicate --config configs/replication/working_paper.toml
```

Use Python 3.11+ and a clean Git checkout. The command currently exits 1 because
research acceptance fails. Its output directory contains the comparison, manifest and
path-level Parquet samples. An unsuccessful replication is retained as evidence.

## Implementation

- Analytical AS quotes, symmetric benchmark and a deterministic Monte Carlo experiment.
- Independent random streams, bootstrap intervals and accounting checks at every step.
- Five validated LOBSTER samples covering 2,110,860 events, with explicit supplied-boundary and timestamp provenance.
- Restartable L3 collection with sequence checks and atomic Parquet output.
- 61 passing tests, strict typing, linting and a pinned environment.

M0 is user-accepted; the live collector evidence remains outstanding. M1 is in progress.
No market backtest, strategy-performance claim or M2 ablation has been completed.

[Operations](docs/OPERATIONS.md) · [M0 evidence](docs/reports/M0.md) · [Decisions](docs/DECISIONS.md) · [State](STATE.md)
