"""Run locally: uv run python scripts/collect_crypto_l3.py [collector options]."""

import sys

from asaudit.cli import app

app(["data", "collect", *sys.argv[1:]])
