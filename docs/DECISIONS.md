# Decisions

## 2026-09-18 Approved initial scope and representation
Context: User approved the M0 plan in this chat.
Decision: Executable prices use integer ticks; timestamps use integer nanoseconds. Derived analytical prices may use floating point with documented units. M0 may proceed without the human-owned golden table and derivation; M1 remains blocked on those inputs. Implement and test the collector here, but leave its real one-hour acceptance run to user hardware.
Status: Approved by the user's “Yes”. No threshold or acceptance criterion was changed.

## 2026-09-18 Bounded sample cannot independently reconstruct every snapshot
Context: PRD §6 M0 requires exact reconstruction at every message index for all five tickers. Proposed interface accepts an initial bounded BookSnapshot and the supplied event stream.
Problem: Official output documentation describes messages within the requested price range. The executed diagnostic finds a previously unseen positive-size boundary price in every sample. Even access to all previous supplied snapshots and the current message does not provide this price or its quantity before the current reference snapshot reveals it. Source acquisition was initially blocked by old URLs returning an application shell, but the official client linked a legacy php.lobsterdata.com host; that access issue is resolved.
Evidence: docs/evidence/source_audit.json records checksums and witness rows: AAPL 48, AMZN 133, GOOG 65, INTC 5, MSFT 8 (one-based CSV rows). No full-depth initial state is supplied by the bounded sample.
Options:
1. Explicit snapshot-assisted bounded replay. Import newly visible boundary state from the corresponding observed snapshot; separately test event-driven changes on observable levels. Retain exact output comparisons but label imported cells as supplied, not independently reconstructed. This changes the acceptance contract and requires an additional order-identity policy before queue simulation.
2. Obtain complete raw order-level events and a sufficient initial state, reconstruct independently, and use LOBSTER only as the reference. Stronger test, with additional data access and preprocessing requirements; free availability has not been verified.
Recommendation: Option 1 for M0's bounded LOBSTER adapter, with explicit provenance and coverage reporting. Do not claim full L3 order identity or independent all-cell reconstruction. Use a separately specified full L3 source for those claims.
Blocked on: User approval of the revised reconstruction acceptance contract or provision of adequate full-depth inputs.

## 2026-09-18 Canonical event schema omits documented source semantics
Context: PRD §5.3 EventType and M0 adapter.
Problem: The official LOBSTER specification includes type 6 cross trades and distinct halt/resume status codes; the PRD enum omits cross trades and its event fields contain no explicit halt status. Treating status price codes as executable prices or silently discarding valid source types would lose meaning. No type 6 or 7 events occurred in the five downloaded samples, so sample success alone would not test these cases.
Options:
1. Extend EventType with CROSS and add an explicit optional halt-status field, with source metadata for values that are not executable prices.
2. Keep the original canonical schema and reject sessions containing unsupported source semantics; document the narrower adapter support.
Recommendation: Option 1, with targeted source-format fixtures after approval.
Blocked on: Approval to extend the canonical schema rather than silently deviating from the PRD.

## 2026-09-18 Approved bounded reconstruction and event schema amendments
Context: User responded “Approved” to both requested amendments in this chat.
Decision: M0 may import explicitly identified boundary state from current reference snapshots while independently checking event-driven observable changes. EventType gains CROSS, and halt status is represented explicitly rather than as an executable price.
Status: Approved. Supersedes the blocked statuses of the two preceding decisions. It does not establish full L3 order identity or FIFO priority.

Implementation detail: LOBSTER price_ticks use its native USD 0.0001 quantum, including sub-cent hidden executions found in the actual samples. The canonical metadata makes the scale explicit. This is an exact source encoding, not a modification of the PRD's later simulator quote increment. No M1 parameter has been populated.

Implementation detail: Python 3.11-compatible NumPy is constrained below 2.4; the complete environment is pinned in uv.lock. The first resolved NumPy exposed Python 3.12-only stub syntax to the Python 3.11 mypy target. This was a dependency compatibility issue, not a scientific or test-criterion change.

## 2026-09-18 Non-integral nanosecond source timestamps
Context: M0 clean-commit validation against all five official level-10 samples.
Problem: The canonical contract requires integer nanoseconds and forbids implicit data repairs. Ten raw timestamps have nonzero sub-nanosecond remainders: AMZN 2, INTC 5, MSFT 3. Each is 0.004 ns from the nearest integer ns. AAPL and GOOG have none. The validator correctly stops rather than truncating or rounding. Serialization noise is a hypothesis, not a verified cause.
Evidence: docs/evidence/m0 contains all five validation manifests, timestamp_precision.json, and its diagnostic manifest. The diagnostic computes differences only; it does not modify input or normalize timestamps.
Options:
1. Approve explicit Decimal-based nearest-nanosecond normalization (ROUND_HALF_EVEN), preserving original source strings and exact deltas in provenance, counting adjusted records and timestamp collisions, and retaining source row order. This sacrifices sub-nanosecond literal precision and must appear in config and manifests. Strict mode should remain available and its rejection test should remain unchanged.
2. Retain strict integer-nanosecond parsing and obtain provider-corrected inputs with verified provenance. This preserves the current contract but requires new source data.
3. Adopt an exact finer-resolution or rational timestamp schema throughout the project. This preserves literal precision but changes the PRD's core types and downstream interfaces.
Recommendation: Option 1, subject to user approval; do not infer a scientific tolerance threshold from these ten records. No rounding policy has been implemented or activated.
Blocked on: Approval of the exact timestamp-normalization policy or provision of corrected inputs. The general instruction to continue was used to finish verification and packaging, not to silently relax this data contract.
