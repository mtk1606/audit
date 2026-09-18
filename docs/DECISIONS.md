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
