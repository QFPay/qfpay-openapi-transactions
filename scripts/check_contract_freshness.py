#!/usr/bin/env python3
"""Fail a release check when the bundled QFPay contract snapshot is incomplete or stale."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-age-days", type=int, default=30)
    parser.add_argument("--today", help="ISO date override for deterministic tests")
    args = parser.parse_args()
    if args.max_age_days < 0:
        raise SystemExit("--max-age-days must not be negative")
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "references" / "contract-manifest.json").read_text(encoding="utf-8"))
    contract = manifest.get("canonical_contract", {})
    required = ("url", "version", "published_at", "locale_index")
    missing = [field for field in required if not contract.get(field)]
    if missing:
        print("contract manifest missing: " + ", ".join(missing))
        return 1
    published_at = date.fromisoformat(contract["published_at"])
    today = date.fromisoformat(args.today) if args.today else date.today()
    age = (today - published_at).days
    if age > args.max_age_days:
        print(f"contract snapshot is {age} days old; maximum is {args.max_age_days}")
        return 1
    print(f"contract snapshot ok: version={contract['version']} age_days={age}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
