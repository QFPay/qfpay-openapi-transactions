from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_contract_source import inspect_document  # noqa: E402


class ContractSourceTests(unittest.TestCase):
    def contract(self, raw: bytes) -> dict:
        return {
            "url": "https://official.example/openapi.json",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "identity_requirement": {"info_title_must_contain": "QFPay"},
            "source_verification": {"status": "verified"},
        }

    def test_accepts_matching_qfpay_document(self) -> None:
        raw = b'{"openapi":"3.1.0","info":{"title":"QFPay OpenAPI","version":"1"},"paths":{}}'
        result = inspect_document(raw, self.contract(raw))
        self.assertTrue(result["verified"], result)

    def test_rejects_a_non_qfpay_document_at_the_same_url(self) -> None:
        raw = b'{"openapi":"3.1.0","info":{"title":"OpenAPI Plant Store","version":"1"},"paths":{}}'
        result = inspect_document(raw, self.contract(raw))
        self.assertFalse(result["verified"])
        self.assertIn("source info.title does not identify the required QFPay contract", result["errors"])


if __name__ == "__main__":
    unittest.main()
