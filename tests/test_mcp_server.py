from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import qfpay_mcp_server as mcp  # noqa: E402


class McpServerTests(unittest.TestCase):
    def test_exposes_only_read_only_tools(self) -> None:
        names = {tool["name"] for tool in mcp.TOOLS}
        self.assertEqual(names, {"qfpay_docs_search", "qfpay_paytypes", "qfpay_transaction_get"})
        self.assertNotIn("qfpay_payment", names)
        self.assertTrue(all(tool["annotations"]["readOnlyHint"] for tool in mcp.TOOLS))

    def test_rejects_credentials_and_invalid_paytype_at_boundary(self) -> None:
        result = mcp.handle_tool_call({"name": "qfpay_transaction_get", "arguments": {"syssn": "ORDER", "client_key": "leak"}})
        self.assertTrue(result["isError"])
        self.assertNotIn("leak", json.dumps(result))
        invalid = mcp.handle_tool_call({"name": "qfpay_paytypes", "arguments": {"pay_type": "BAD"}})
        self.assertTrue(invalid["isError"])

    def test_safe_transaction_preview_and_pii_redaction(self) -> None:
        preview = mcp.handle_tool_call({"name": "qfpay_transaction_get", "arguments": {"out_trade_no": "ORDER_1001"}})
        self.assertFalse(preview["isError"])
        self.assertEqual(preview["structuredContent"]["environment"], "qa")
        self.assertNotIn("ORDER_1001", json.dumps(preview))
        redacted = mcp.mcp_result({"email": "merchant@example.com", "mchid": "STORE", "nested": {"buyer_id": "buyer"}})
        self.assertNotIn("merchant@example.com", json.dumps(redacted))
        self.assertNotIn("STORE", json.dumps(redacted))

    def test_normalizes_uncertain_state(self) -> None:
        result = mcp.normalize_query_response(200, '{"respcd":"1298","out_trade_no":"ORDER"}')
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertIn("Do not retry", result["recovery"])


if __name__ == "__main__":
    unittest.main()
