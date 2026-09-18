"""Diagnose source timestamp precision without changing any source value."""

import argparse
import csv
import json
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from asaudit.logging import RunManifest, file_hash


def inspect(path: Path) -> dict[str, object]:
    examples: list[dict[str, object]] = []
    count = 0
    maximum = Decimal(0)
    with path.open() as handle:
        for index, row in enumerate(csv.reader(handle), 1):
            exact_ns = Decimal(row[0]) * Decimal(1000000000)
            nearest = exact_ns.to_integral_value(rounding=ROUND_HALF_EVEN)
            if exact_ns != nearest:
                count += 1
                distance = abs(exact_ns - nearest)
                maximum = max(maximum, distance)
                if len(examples) < 3:
                    examples.append(
                        {
                            "row_1based": index,
                            "raw_seconds": row[0],
                            "distance_to_nearest_ns": str(distance),
                        }
                    )
    return {
        "symbol": path.name.split("_")[0],
        "noninteger_nanosecond_rows": count,
        "max_distance_to_nearest_ns": str(maximum),
        "examples": examples,
        "source_sha256": file_hash(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("data/raw/lobster"))
    parser.add_argument("--output", type=Path, default=Path("results"))
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    run = RunManifest(
        args.output,
        {
            "purpose": "source_timestamp_diagnostic",
            "normalization_performed": False,
            "data_root": str(args.data_root.resolve()),
        },
        args.allow_dirty,
        "five-source-samples",
    )
    paths = sorted(args.data_root.glob("*message_10.csv"))
    if len(paths) != 5:
        run.finish("failed", error="expected five message files")
        raise ValueError("expected five message files")
    records = [inspect(path) for path in paths]
    report = {
        "purpose": "deterministic source-format audit; no normalization performed",
        "records": records,
    }
    out = run.directory / "timestamp_precision.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    run.finish(
        "passed", data_checksums={str(p): file_hash(p) for p in paths}, report_sha256=file_hash(out)
    )
    print(run.directory)


if __name__ == "__main__":
    main()
