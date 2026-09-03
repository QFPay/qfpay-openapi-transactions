#!/usr/bin/env python3
"""Check that bundled QFPay references mention every documented pay_type."""

import re
import sys
from pathlib import Path


OFFICIAL_PAYTYPES_2026_09_03 = {
    "800008",
    "800101",
    "800108",
    "801101",
    "801107",
    "801110",
    "801501",
    "801510",
    "801512",
    "801514",
    "800201",
    "800208",
    "800207",
    "800212",
    "800210",
    "800213",
    "805801",
    "805808",
    "805814",
    "805812",
    "800701",
    "800708",
    "800712",
    "800714",
    "802001",
    "802010",
    "803701",
    "803712",
    "803714",
    "802801",
    "802808",
    "806527",
    "806708",
    "806808",
}

PAGE_SPECIFIC_PAYTYPES = {
    "800107",
    "801008",
    "805810",
    "800710",
}

REFERENCE_FILES = (
    "references/qfpay-openapi-reference.zh-CN.md",
    "references/qfpay-openapi-reference.md",
)


def paytypes_in(path):
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r"\b\d{6}\b", text))


def main():
    root = Path(__file__).resolve().parents[1]
    required = OFFICIAL_PAYTYPES_2026_09_03 | PAGE_SPECIFIC_PAYTYPES
    failed = False

    for relpath in REFERENCE_FILES:
        path = root / relpath
        found = paytypes_in(path)
        missing_official = sorted(OFFICIAL_PAYTYPES_2026_09_03 - found)
        missing_page_specific = sorted(PAGE_SPECIFIC_PAYTYPES - found)
        if missing_official or missing_page_specific:
            failed = True
            print(f"{relpath}: missing")
            if missing_official:
                print("  official:", ", ".join(missing_official))
            if missing_page_specific:
                print("  page-specific:", ", ".join(missing_page_specific))
        else:
            print(f"{relpath}: ok ({len(required)} documented paytypes covered)")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
