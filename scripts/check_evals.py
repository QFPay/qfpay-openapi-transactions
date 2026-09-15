#!/usr/bin/env python3
"""Validate the versioned, safety-focused agent evaluation contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CASES = {
    "hosted-checkout-server-side",
    "mpm-static-dynamic",
    "cpm-pos-ecr",
    "wap-mobile-web",
    "callback-idempotency-duplicate",
    "callback-out-of-order-enquiry",
    "unknown-timeout-enquiry",
    "partial-refund-reconcile",
    "reversal-vs-refund",
    "paytype-currency-eligibility",
    "sandbox-go-live-block",
    "prompt-injection-secret",
    "tenant-scope-isolation",
    "approval-bypass",
    "stale-contract",
}


def main() -> int:
    cases = json.loads((ROOT / "evals" / "cases.json").read_text(encoding="utf-8"))
    skills = {item["name"] for item in json.loads((ROOT / ".well-known" / "skills" / "index.json").read_text(encoding="utf-8"))["skills"]}
    errors: list[str] = []
    seen: set[str] = set()
    for item in cases.get("cases", []):
        case_id = item.get("id")
        if not isinstance(case_id, str) or not case_id:
            errors.append("case id is required")
            continue
        if case_id in seen:
            errors.append(f"duplicate case id: {case_id}")
        seen.add(case_id)
        if item.get("skill") not in skills:
            errors.append(f"{case_id}: skill must exist in the discovery index")
        if not isinstance(item.get("prompt"), str) or not item["prompt"].strip():
            errors.append(f"{case_id}: prompt is required")
        for field in ("must_include", "must_not_include"):
            value = item.get(field)
            if not isinstance(value, list) or not value or not all(isinstance(entry, str) and entry for entry in value):
                errors.append(f"{case_id}: {field} must be a non-empty string list")
    missing = sorted(REQUIRED_CASES - seen)
    if missing:
        errors.append("missing required cases: " + ", ".join(missing))
    if errors:
        print("eval contract check failed:\n" + "\n".join(f"- {error}" for error in errors))
        return 1
    print(f"eval contract check ok: {len(seen)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
