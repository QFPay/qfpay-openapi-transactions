#!/usr/bin/env python3
"""Check the local release evidence; public mode intentionally enforces stricter gates."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def run_check(script: str, *args: str) -> list[str]:
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / script), *args], cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode == 0:
        return []
    detail = (result.stdout + result.stderr).strip().replace("\n", "; ")
    return [f"{script} failed: {detail}"]


def repository_url(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("url"), str):
        return value["url"]
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true", help="verify the internal preview package without asserting public metadata")
    args = parser.parse_args()

    errors: list[str] = []
    for script, script_args in (
        ("check_contract_freshness.py", ()),
        ("check_paytype_coverage.py", ()),
        ("check_skill_release.py", ()),
        ("check_evals.py", ()),
        ("build_release_manifest.py", ("--check",)),
    ):
        errors.extend(run_check(script, *script_args))

    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    index = json.loads((ROOT / ".well-known" / "skills" / "index.json").read_text(encoding="utf-8"))
    contract = json.loads((ROOT / "references" / "contract-manifest.json").read_text(encoding="utf-8"))["canonical_contract"]
    if package.get("version") != index.get("release"):
        errors.append("package.json version must match the skills index release")
    if args.preview:
        if errors:
            print("preview release check failed:\n" + "\n".join(f"- {error}" for error in errors))
            return 1
        print("preview release check ok: internal package remains non-public and Sandbox-first")
        return 0

    if package.get("private") is not False:
        errors.append("package.json must set private to false before a public release")
    if not isinstance(package.get("license"), str) or package["license"] == "UNLICENSED":
        errors.append("choose an approved SPDX license before a public release")
    if not (ROOT / "LICENSE").is_file():
        errors.append("LICENSE is required before a public release")
    if not isinstance(package.get("homepage"), str) or not package["homepage"].startswith("https://"):
        errors.append("package.json requires an official HTTPS homepage before a public release")
    if not repository_url(package.get("repository")).startswith("https://"):
        errors.append("package.json requires an official HTTPS repository URL before a public release")
    if not SHA256.fullmatch(contract.get("sha256", "")):
        errors.append("canonical_contract.sha256 must be refreshed from the official OpenAPI document before a public release")
    if contract.get("source_verification", {}).get("status") != "verified":
        errors.append("canonical contract source identity must be verified against an official QFPay OpenAPI URL before a public release")
    if not (ROOT / "CHANGELOG.md").is_file():
        errors.append("CHANGELOG.md is required before a public release")

    git = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True, check=False)
    if git.returncode or git.stdout.strip():
        errors.append("public release must be built from a clean, reviewed Git tag")

    if errors:
        print("public release check failed:\n" + "\n".join(f"- {error}" for error in errors))
        return 1
    print("public release check ok: technical gates passed; complete the human approvals in docs/PUBLISHING.md before publishing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
