#!/usr/bin/env python3
"""Validate the versioned Skill index and plugin manifest without external dependencies."""

from __future__ import annotations

import json
import re
from pathlib import Path


SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 4 or lines[0] != "---":
        raise ValueError(f"{path}: missing YAML frontmatter")
    values = {}
    for line in lines[1:]:
        if line == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip('"')
    return values


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    index = json.loads((root / ".well-known" / "skills" / "index.json").read_text(encoding="utf-8"))
    plugin = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    contract = json.loads((root / "references" / "contract-manifest.json").read_text(encoding="utf-8"))["canonical_contract"]
    errors = []
    release = index.get("release", "")
    if SEMVER.fullmatch(release) is None:
        errors.append("skill index release must use strict semver")
    if plugin.get("version") != release:
        errors.append("plugin version must match skill index release")
    if package.get("version") != release:
        errors.append("package version must match skill index release")
    if index.get("contract_version") != contract.get("version"):
        errors.append("skill index contract_version must match the canonical contract")
    names = set()
    for skill in index.get("skills", []):
        name = skill.get("name", "")
        if name in names:
            errors.append(f"duplicate skill name: {name}")
        names.add(name)
        if skill.get("version") != release:
            errors.append(f"{name}: version must match release")
        path = root / skill.get("path", "") / "SKILL.md"
        if not path.is_file():
            errors.append(f"{name}: SKILL.md is missing")
            continue
        metadata = frontmatter(path)
        if metadata.get("name") != name:
            errors.append(f"{name}: frontmatter name does not match index")
        if not metadata.get("description"):
            errors.append(f"{name}: frontmatter description is required")
    if errors:
        print("skill release check failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"skill release check ok: {len(names)} skills at {release}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
