#!/usr/bin/env python3
"""Verify that a downloaded OpenAPI document is the declared QFPay contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


def inspect_document(raw: bytes, contract: dict) -> dict:
    errors: list[str] = []
    try:
        document = json.loads(raw)
    except json.JSONDecodeError:
        document = {}
        errors.append("source is not valid JSON")
    info = document.get("info", {}) if isinstance(document, dict) else {}
    title = info.get("title", "") if isinstance(info, dict) else ""
    version = info.get("version", "") if isinstance(info, dict) else ""
    required_title = contract.get("identity_requirement", {}).get("info_title_must_contain", "")
    actual_hash = hashlib.sha256(raw).hexdigest()
    if not isinstance(document, dict) or not document.get("openapi"):
        errors.append("source is not an OpenAPI document")
    if not required_title or required_title.casefold() not in str(title).casefold():
        errors.append("source info.title does not identify the required QFPay contract")
    expected_hash = contract.get("sha256", "")
    if expected_hash != actual_hash:
        errors.append("source SHA-256 does not match canonical_contract.sha256")
    if contract.get("source_verification", {}).get("status") != "verified":
        errors.append("canonical source_verification.status is not verified")
    return {
        "url": contract.get("url"),
        "sha256": actual_hash,
        "expected_sha256": expected_hash,
        "openapi": document.get("openapi") if isinstance(document, dict) else None,
        "info_title": title,
        "info_version": version,
        "path_count": len(document.get("paths", {})) if isinstance(document, dict) and isinstance(document.get("paths", {}), dict) else 0,
        "verified": not errors,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-file", type=Path, help="inspect a locally downloaded official OpenAPI document")
    parser.add_argument("--timeout", type=float, default=15, help="HTTPS fetch timeout in seconds")
    args = parser.parse_args()
    contract = json.loads((ROOT / "references" / "contract-manifest.json").read_text(encoding="utf-8"))["canonical_contract"]
    try:
        if args.from_file:
            raw = args.from_file.read_bytes()
        else:
            request = Request(contract["url"], headers={"User-Agent": "qfpay-payment-skills-contract-verifier/0.2"})
            with urlopen(request, timeout=args.timeout) as response:  # nosec B310: URL is versioned repository metadata
                raw = response.read()
        result = inspect_document(raw, contract)
    except (OSError, ValueError) as error:
        print(json.dumps({"verified": False, "errors": [str(error)]}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
