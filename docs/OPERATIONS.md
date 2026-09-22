# Operating instructions

Python 3.11+ and uv are required. This session used Python 3.12.

```bash
uv sync --locked
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy --strict src
uv run pytest -q
```

The GitHub Actions workflow executes this gate on push and pull requests. Remote CI has not been run in this session.

## Fetch and validate the public samples

```bash
uv run python scripts/fetch_lobster_sample.py
uv run asaudit data validate --source lobster --symbol AAPL --date 2012-06-21 --config configs/data/lobster.toml
```

Run from the clean repository root. Select AMZN, GOOG, INTC, and MSFT with `--symbol`. Source, symbol and date select source files; quality policy, depth, price scale, and reconstruction mode come from `--config configs/data/lobster.toml` or strict defaults. The sample config explicitly selects `nearest_ns`; without a config, timestamp parsing remains strict. Paths can be changed with `--data-root` and `--output`. A dirty checkout is rejected unless `--allow-dirty` is supplied and recorded.

The fetcher checks the pinned archive SHA-256 values before extracting CSVs. It refuses silently changed source archives. Raw samples are not redistributed here. Check applicable data terms before redistributing any source slice.

Each validation run writes an atomic `manifest.json`, configuration hash, input checksums, environment versions, Git SHA, elapsed time, quality counts, and JSON logs under `results/`. Failures retain a traceback and partial quality counts when available. CLI quality reports are JSON; progress logs go to stderr.

## What reconstruction proves

The first post-message snapshot is explicitly supplied as the initial state; its first message is decoded but not applied twice. For subsequent rows, visible event-driven volume changes and retained levels must match exactly. A newly exposed deeper boundary level may be supplied by that row's reference snapshot and is marked accordingly. `ReconstructionResult.supplied_levels` identifies its side, price and size. Interior insertion, unsupported disappearance, impossible removal, and changed retained volume fail validation.

The validator is an ingestion check. It does not provide full order identities, queue priority, or a backtest. Imported boundary cells are not independent validation evidence. Snapshot data at an event time must not be used by a future strategy before that event arrives.

Prices are integer source quanta: one LOBSTER unit is USD 0.0001. This preserves sub-cent hidden executions exactly. This encoding is distinct from the venue's quote increment; no strategy tick-size setting has been changed. Derived mid and microprice values are in these same units. Timestamps are integer epoch nanoseconds, converted from New York session time without floating-point arithmetic. The approved `nearest_ns` policy uses Decimal with half-even rounding. It preserves original source strings and exact signed adjustments, counts adjusted records and newly merged timestamps, and retains source row order. Source clock reversals still fail, including reversals that round to the same nanosecond.

CROSS is retained as a distinct event. HALT has an explicit status and no executable price. Neither is silently converted into a visible execution. The current bounded book treats them as non-mutating and will reject a paired snapshot requiring an unexplained change. Such source cases require an explicit extension, not a silent repair.

LOBSTER has no exchange sequence numbers. `sequence_gaps: null` means unavailable, never zero. Its configured sequence-gap threshold cannot be evaluated from this format. Coinbase detects and aborts each non-contiguous segment, preserving the gap record.

## Run the collector locally

```bash
uv run python scripts/collect_crypto_l3.py --config configs/collector/coinbase.toml
```

The config specifies a one-hour capture. Output is raw full-channel messages plus L3 snapshots, stored as Parquet under `symbol/date/hour` partitions using UTC receive time. Exchange timestamps and sequence numbers are retained separately. No order routing exists.

The collector subscribes and buffers before fetching each snapshot, discards only pre-snapshot overlap, verifies subsequent sequence continuity, and restarts with a new segment after a disconnect. Complete Parquet chunks are atomically committed with unique names. Pending in-memory rows can be lost on a hard kill; an unclosed segment is not a certified complete session. Restart always creates a new snapshot segment and never overwrites previous chunks.

Disconnects remain explicit. A snapshot restores current book state, not missing historical events. The collector returns nonzero for an interrupted/incomplete run even if later segments collect successfully. It does not assert that a forced-disconnect run has gap-free history. A real one-hour acceptance run and that stricter recovery claim remain unresolved; the local transport fixture is not a substitute.

## Working-paper replication audit

```bash
uv run asaudit replicate --config configs/replication/working_paper.toml
```

The reference file keeps its supplied name `tests/golden/as2008_table.json`, but
its contents identify the October 2006 working paper. Do not infer publication
version from the filename. The user has authorized the build agent to write the
derivation and make the remaining implementation decisions, superseding the
original authorship restriction. The original supplied spec files are retained
as historical inputs; dated amendments are recorded in `docs/DECISIONS.md`.

The command records three cases per source table: strict equation-based primary
simulation, equation spread with explicit probability saturation, and constant
liquidity spread with saturation. The latter two are diagnostic interpretations.
Each strategy and each bootstrap has an independent seed child. Config controls
the root seed, path count and bootstrap count. A path count other than the source's
1,000 is explicitly ineligible for acceptance.

Exit 1 with manifest status `not_reproduced` is the expected current result.
It is distinct from an unexpected run failure. The output includes the target
comparisons, pointwise bootstrap intervals, variance ratios, raw probability
exceedances, terminal paths and their checksums. See `docs/reports/M1.md`.

## Project boundaries

M1 includes theoretical strategy quotes, a derivation and synthetic experiments.
Numerical replication remains unresolved. No holdout access, market calibration,
M2 simulator or preregistration was added.

## Published 2008 comparison

For the current M1 source, supply both arguments:

```bash
uv run asaudit replicate --config configs/replication/qf2008.toml --reference tests/golden/as2008_table_qf2008.json
```

The legacy defaults remain the 2006 working-paper audit. Published runs instead
use the constant continuous time-average spread for the symmetric benchmark,
the source's gamma=1 third table, and independent random streams under namespace
(2008,). Both input tables are preserved byte-for-byte. The published run currently
exits 1 because strict acceptance remains incomplete; see `docs/reports/M1-qf2008.md`.
