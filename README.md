# as-audit

Research infrastructure for auditing the Avellaneda-Stoikov market-making model against observed order-book data.

The project asks how queue position, adverse selection, and competing liquidity affect model performance. The current build covers data ingestion, validation, and reproducible capture. Strategy replication and performance results come later.

## Run

```bash
uv sync --locked
uv run python scripts/fetch_lobster_sample.py
uv run asaudit data validate --symbol AAPL --date 2012-06-21 --config configs/data/lobster.toml
```

Run from a clean Git checkout with Python 3.11 or newer. Each run records its configuration, source checksums, code revision, and validation results.

## Engineering

- Integer source prices and nanosecond timestamps, with explicit normalization provenance.
- Snapshot-assisted reconstruction that identifies supplied boundary levels separately from independent checks.
- Restartable Coinbase L3 capture with sequence checks and atomic Parquet output.
- Property tests, corruption tests, strict typing, and a pinned environment.

## Status

**48 tests pass. All five sample sessions validate.**

| Sample | Events | Result |
|---|---:|---|
| AAPL | 400,391 | Pass |
| AMZN | 269,748 | Pass |
| GOOG | 147,916 | Pass |
| INTC | 624,040 | Pass |
| MSFT | 668,765 | Pass |

Validation uses the approved snapshot-assisted boundary and timestamp policies. The live one-hour collector test remains pending. No strategy returns or research findings are claimed.

The [M0 report](docs/reports/M0.md) links the results to their manifests and documents the limits of each check.

[Operating instructions](docs/OPERATIONS.md) · [Data provenance](docs/DATA.md) · [Decisions](docs/DECISIONS.md) · [Project state](STATE.md)
