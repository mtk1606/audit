"""Source-feasibility diagnostic, not the M0 adapter or a research experiment.

Usage: python scripts/audit_sample_boundaries.py /path/to/download/cache
Downloads the provider's five level-10 sample archives if absent. Emits JSON.
Never uses or constructs a holdout path. No raw data is redistributed.
"""

import csv
import hashlib
import io
import json
import sys
import urllib.request
import zipfile
from itertools import zip_longest
from pathlib import Path


def inspect(symbol: str, cache: Path) -> dict[str, object]:
    url = (
        "https://php.lobsterdata.com/info/sample/"
        f"LOBSTER_SampleFile_{symbol}_2012-06-21_10.zip"
    )
    path = cache / f"{symbol}.zip"
    if not path.exists():
        with urllib.request.urlopen(url, timeout=60) as response:
            path.write_bytes(response.read())
    raw = path.read_bytes()
    seen: set[int] = set()
    witness: dict[str, object] | None = None
    counts: dict[str, int] = {}
    count = 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        messages = [
            n for n in archive.namelist() if "message" in n and n.endswith(".csv")
        ]
        books = [
            n for n in archive.namelist() if "orderbook" in n and n.endswith(".csv")
        ]
        if len(messages) != 1 or len(books) != 1:
            raise ValueError("Expected exactly one message and one orderbook CSV")
        with (
            archive.open(messages[0]) as message_file,
            archive.open(books[0]) as book_file,
        ):
            pairs = zip_longest(
                csv.reader(io.TextIOWrapper(message_file)),
                csv.reader(io.TextIOWrapper(book_file)),
            )
            for index, (event, snapshot) in enumerate(pairs, 1):
                if event is None or snapshot is None:
                    raise ValueError("Message and snapshot row counts differ")
                if len(event) != 6 or len(snapshot) != 40:
                    raise ValueError("Unexpected source column count")
                row = list(map(int, snapshot))
                count += 1
                counts[event[1]] = counts.get(event[1], 0) + 1
                seen.add(int(event[4]))  # Include current event before checking.
                if index > 1 and witness is None:
                    for offset, side in [(0, "ask"), (2, "bid")]:
                        for price, size in zip(
                            row[offset::4], row[offset + 1 :: 4], strict=True
                        ):
                            if size > 0 and price not in seen:
                                witness = {
                                    "row_1based": index,
                                    "side": side,
                                    "price_raw": price,
                                    "size_shares": size,
                                    "event_type": event[1],
                                    "event_price_raw": int(event[4]),
                                    "seen_in_prior_messages_or_snapshots": False,
                                }
                                break
                        if witness is not None:
                            break
                # This deliberately grants ALL past snapshots, more information
                # than the proposed event-only reconstruction would possess.
                seen.update(row[0::4])
                seen.update(row[2::4])
    return {
        "symbol": symbol,
        "url": url,
        "archive_sha256": hashlib.sha256(raw).hexdigest(),
        "event_count": count,
        "event_type_counts": counts,
        "first_unseen_boundary": witness,
    }


if __name__ == "__main__":
    cache_dir = Path(sys.argv[1])
    cache_dir.mkdir(parents=True, exist_ok=True)
    results = [inspect(s, cache_dir) for s in ["AAPL", "AMZN", "GOOG", "INTC", "MSFT"]]
    print(json.dumps(results, indent=2, sort_keys=True))
