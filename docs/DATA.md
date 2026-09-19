# Data provenance and source constraints

Sources accessed during this session:
- https://php.lobsterdata.com/info/DataStructure.php: primary output schema.
- https://php.lobsterdata.com/info/DataSamples.php: primary sample catalog.
- https://docs.cdp.coinbase.com/exchange/websocket-feed/channels: full-channel buffering and snapshot initialization; non-resting done/change messages must not mutate the book.
- https://github.com/rhuang10/lobsterdata/blob/main/README.md: client linked by the provider; identifies its legacy host.

The sample catalog confirms AMZN, AAPL, GOOG, INTC, and MSFT on 2012-06-21 at levels 1, 5, and 10. Level-10 archives were downloaded and inspected; URLs and SHA-256 hashes appear in source_audit.json. Samples were used only for structural feasibility checks, before any scientific split is defined. No holdout directory was accessed.

Do not redistribute raw samples until the applicable data licence is checked. This archive contains the diagnostic and limited audit metadata, not raw CSVs or downloaded ZIPs.

The six-column LOBSTER message format has no exchange sequence field. Missing-message detection cannot simply be reported as zero sequence gaps; the adapter must distinguish unavailable sequence evidence from verified continuity. Exact row alignment can be checked, but it does not prove the source has no omitted exchange messages.

Coinbase snapshot synchronization restores current book state; it does not recreate every missed event during an outage. A future collector must preserve the discontinuity and must not label a snapshot-recovered event history gap-free without an independently verified recovery mechanism. The collector's one-hour run remains external and pending.
