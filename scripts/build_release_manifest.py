#!/usr/bin/env python3
"""Build or verify a deterministic integrity manifest for the npm package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "release" / "manifest.json"
SELF_PATH = "release/manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def packed_files(root: Path) -> list[dict[str, Any]]:
    """Return npm's actual dry-run file list, excluding this self-referential manifest."""
    cache = Path(tempfile.gettempdir()) / "qfpay-npm-cache"
    cache.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.setdefault("npm_config_cache", str(cache))
    result = subprocess.run(
        ["npm", "pack", "--dry-run", "--json"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "npm pack --dry-run failed")
    try:
        packed = json.loads(result.stdout)
        files = packed[0]["files"]
    except (IndexError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("npm pack --dry-run returned an unexpected manifest") from error

    entries = []
    for item in files:
        relpath = item.get("path")
        if not isinstance(relpath, str) or relpath == SELF_PATH:
            continue
        candidate = (root / relpath).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError as error:
            raise RuntimeError(f"npm selected a path outside the package: {relpath}") from error
        if not candidate.is_file():
            raise RuntimeError(f"npm selected a missing file: {relpath}")
        entries.append({"path": relpath, "size": candidate.stat().st_size, "sha256": sha256(candidate)})
    return sorted(entries, key=lambda entry: entry["path"])


def manifest(root: Path) -> dict[str, Any]:
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    plugin = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    contract = json.loads((root / "references" / "contract-manifest.json").read_text(encoding="utf-8"))["canonical_contract"]
    return {
        "schema_version": 1,
        "package": {"name": package["name"], "version": package["version"]},
        "plugin": {"name": plugin["name"], "version": plugin["version"]},
        "contract": {
            "version": contract["version"],
            "url": contract["url"],
            "sha256": contract.get("sha256", ""),
            "source_verification": contract.get("source_verification", {}).get("status", ""),
        },
        "integrity_exclusions": [SELF_PATH],
        "files": packed_files(root),
    }


def encoded(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="manifest path (default: release/manifest.json)")
    parser.add_argument("--check", action="store_true", help="fail unless the saved manifest exactly matches the package")
    parser.add_argument("--stdout", action="store_true", help="write the generated JSON to stdout instead of a file")
    args = parser.parse_args()
    if args.check and args.stdout:
        raise SystemExit("--check and --stdout cannot be used together")

    try:
        generated = encoded(manifest(ROOT))
    except (OSError, RuntimeError, KeyError, json.JSONDecodeError) as error:
        print(f"release manifest failed: {error}", file=sys.stderr)
        return 1

    output = args.output if args.output.is_absolute() else (ROOT / args.output)
    if args.stdout:
        print(generated, end="")
        return 0
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != generated:
            print(f"release manifest is stale or missing: {output.relative_to(ROOT)}")
            return 1
        print(f"release manifest ok: {output.relative_to(ROOT)}")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generated, encoding="utf-8")
    print(f"release manifest written: {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
