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

## 2026-09-19 Timestamp normalization approved
Context: The user approved explicit nearest-nanosecond normalization and requested concise professional writing without em dashes.
Decision: Add the nearest_ns policy using Decimal and ROUND_HALF_EVEN. Preserve each original timestamp and signed adjustment. Count adjusted records and newly merged timestamps; preserve source row order and reject source clock reversals even when rounded timestamps tie. Strict mode and its original rejection tests remain unchanged.
Configuration: The sample config opts into nearest_ns. The decoder and CLI defaults remain strict. Every run records the resolved policy and adjustment provenance.
Status: Approved and implemented. Supersedes the timestamp policy blocker above. Real sample verification follows this commit.
Presentation: Use a concise README, a compact evidence table, and separate operating instructions. Preserve original supplied specifications as source documents.

## 2026-09-19 Timestamp policy verified
All five clean-commit validation runs pass. Ten adjustments were recorded, each 0.004 ns in magnitude, with zero newly merged timestamps. Evidence is preserved in docs/evidence/m0-normalization. The timestamp blocker is resolved under the approved policy. The live collector acceptance item remains open.

## 2026-09-22 M0 accepted; implementation authority expanded
Context: The user explicitly accepted M0 and directed the move to M1, then
explicitly overrode the build instructions for the derivation and remaining work.
Decision: Record M0 as user-accepted with the live collector evidence still absent.
Author the derivation and choose explicit implementation and statistical conventions
without another approval pause. Do not represent missing evidence as a passing test.
The supplied golden table is copied byte-for-byte and its human-verification flag
remains false. No holdout data is accessed.

## 2026-09-22 Working-paper experiment protocol
Context: The attached source is dated October 5, 2006, not the 2008 publication.
Decision made before the first full run: seed 20260922, 1000 paths per strategy
and case, 2000 pathwise percentile bootstrap resamples, pointwise 95% intervals,
sample standard deviations with ddof=1. Independent SeedSequence children for
each strategy/case simulation, bootstrap and variance-ratio bootstrap. No seed
search and no tuning against target values. The ratio is symmetric profit
variance divided by inventory-strategy profit variance; the PRD's 10% tolerance
is retained. The default comparison treats source point estimates as targets,
without claiming to know uncertainty from the paper's unavailable raw paths.
Primary case: equation 3.18 spread and strict Bernoulli probability validity.
Diagnostic cases: equation spread with explicit probability saturation, and
constant liquidity spread with explicit saturation. Diagnostics cannot satisfy
primary acceptance. Profit is terminal cash plus marked inventory, less initial
marked wealth. Fills use old quotes before the independent binary mid move.
Continuous model prices and time use floating-point arithmetic in M1 only;
integer market-data and future execution interfaces remain unchanged.
Source ambiguities: table spreads omit the risk term; side dependence and seeds
are unspecified; lambda*dt can exceed one. Any failed replication remains a
reported failure. The 2008 published-version claim is withheld.

## 2026-09-22 M1 experiment outcome
The fixed protocol ran from clean commit 2b75c0b and exited 1 with status
not_reproduced. Primary inventory runs at gamma 0.1 and 0.5 encounter invalid
Bernoulli probabilities. The gamma 0.01 primary comparison also misses targets.
Neither diagnostic interpretation satisfies all numerical checks. Preserve all
results in docs/evidence/m1/run. M1 remains in progress; no M2 implementation or
verified-replication publication follows from these results. A source-faithful
resolution requires stronger evidence about the numerical procedure, not tuning
the simulator to the target table.
