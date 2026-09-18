"""Fetch the five pinned sample archives and extract only the paired CSVs.

No raw data is committed. Run: uv run python scripts/fetch_lobster_sample.py
"""

import argparse
import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/raw/lobster"))
    parser.add_argument("--cache", type=Path, default=Path("data/downloads"))
    args = parser.parse_args()
    records = json.loads(
        (Path(__file__).resolve().parents[1] / "docs/evidence/source_audit.json").read_text()
    )
    args.output.mkdir(parents=True, exist_ok=True)
    args.cache.mkdir(parents=True, exist_ok=True)
    for record in records:
        archive_path = args.cache / f"{record['symbol']}.zip"
        if not archive_path.exists():
            tmp = archive_path.with_suffix(".partial")
            with (
                urllib.request.urlopen(record["url"], timeout=60) as response,
                tmp.open("wb") as out,
            ):
                shutil.copyfileobj(response, out)
            tmp.replace(archive_path)
        digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        if digest != record["archive_sha256"]:
            raise ValueError(
                f"source checksum changed for {record['symbol']}; do not accept silently"
            )
        with zipfile.ZipFile(archive_path) as archive:
            members = [n for n in archive.namelist() if n.endswith(".csv")]
            if len(members) != 2:
                raise ValueError("expected exactly two CSV members")
            for member in members:
                path = args.output / Path(member).name
                with archive.open(member) as src, path.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
        print(f"{record['symbol']}: verified {digest}")


if __name__ == "__main__":
    main()
