# M0 implementation and verification report

M0 infrastructure is implemented and the local engineering gate passes. M0 acceptance remains incomplete: only AAPL and GOOG finish strict timestamp validation, and the collector has not run live for one hour. No market-making strategy or research performance result exists.

## Implemented scope

Typed canonical events, immutable dataclass contracts, four model protocols, exact LOBSTER decoding, approved snapshot-assisted bounded reconstruction with per-level provenance, quality reporting and contextual failures, Typer validation and collection commands, structured logging, atomic manifests, a uv lockfile, and CI configuration. The raw Coinbase full-channel collector buffers before snapshot initialization, checks sequence continuity, writes atomic partitioned Parquet chunks, and reconnects into a new explicitly discontinuous segment. It does not implement trading or a normalized crypto replay simulator.

## Actual checks

All 32 local tests pass. Tests include property-based timestamp and cancellation arithmetic, malformed source data, corruption of retained levels, improper interior boundary injection, explicit provenance, hidden sub-cent price preservation, CROSS and HALT decoding, snapshot overlap, late stale sequences, gap journaling, safe restart, failure manifests, and a real loopback HTTP/WebSocket forced disconnect. The exact local gate output is in docs/evidence/m0/gate.txt. A clean export of tracked commit 20652c0 was installed into a fresh virtual environment using the lockfile and passed the same gate (export-gate.txt). The initial offline setup lacked cached wheels; a normal pinned install succeeded. CI is configured, not remotely executed.

The first test run failed at imports because no package existed. Additional regression tests were observed failing before fixes for stale sequence acceptance, missing boundary provenance, impossible boundary volume, and missing partial failure counters. No assertions were deleted, skipped, weakened, or xfailed.

## Real source acceptance

Five validation runs reference clean source commit 0260c03. Later adapter edits are formatting and datetime.UTC alias changes only. Each run records source CSV hashes and config.

| Symbol | Result | Rows successfully validated | First rejected CSV row |
|---|---|---:|---:|
| AAPL | Pass | 400391 | none |
| GOOG | Pass | 147916 | none |
| AMZN | Fail at timestamp precision | 29331 | 29332 |
| INTC | Fail at timestamp precision | 178416 | 178417 |
| MSFT | Fail at timestamp precision | 7814 | 7815 |

These are exhaustive structural counts, not statistical research estimates. No bootstrap CI or P&L claim applies. All records after the first invalid row remain unvalidated by the paired validator, even though a separate diagnostic scanned timestamp strings across the complete files.

AAPL has 7903238 independently checked level observations, 104562 supplied boundary levels, and 20 supplied initial levels. GOOG has 2913849 independently checked observations, 44451 supplied boundary levels, and 20 supplied initial levels. Supplied levels must not be described as independent reconstruction. There is no exchange sequence field in LOBSTER; sequence_gaps is null, not zero.

## Adversarial review

BLOCKER: Ten non-integral nanosecond timestamps require a user-owned policy decision before all-five acceptance can pass. No silent repair was introduced.

SUSPECT: Bounded aggregate snapshots cannot establish initial individual order identities or FIFO positions. M2 must not treat this adapter as full L3 queue truth.

SUSPECT: A reconnect snapshot does not reconstruct missed event history. Tests prove local restart mechanics, not a gap-free one-hour exchange capture. Interrupted runs are marked incomplete and return nonzero.

Resolved: Reference-fed boundary levels are distinguished from independently checked levels. Unexpected interior inserts and favorable volume corruption fail. A stale post-start sequence is not mistaken for buffered snapshot overlap. The raw-data ignore rule was anchored to the repository root so source adapters and configs are included. A tracked-file export is verified separately to guard against workspace-only success.

Not yet applicable: Accounting drift, optimistic strategy fills, split leakage, seed reuse across configurations, and unusually favorable research results. No simulator, calibration, split, RNG-based experiment or strategy measurement has been introduced. No holdout directory was read. Human-owned files remain untouched.

## Remaining work

Resolve the timestamp policy and rerun the three failed symbols without weakening strict-mode tests. Run the supplied collector locally for the required duration and retain its manifest and capture. Do not advance to M1 until M0 is accepted; M1 additionally requires the human-owned golden table and derivation.
