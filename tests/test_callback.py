from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from qfpay_callback import callback_summary, replay_callback, verify_callback  # noqa: E402


class CallbackTests(unittest.TestCase):
    def test_uses_raw_body_and_does_not_echo_payload(self) -> None:
        body = b'{"email":"buyer@example.com","syssn":"123"}'
        key = "secret"
        signature = hashlib.md5(body + key.encode()).hexdigest().upper()
        self.assertTrue(verify_callback(body, key, signature))
        summary = callback_summary(body, key, signature)
        self.assertTrue(summary["valid"])
        self.assertNotIn("buyer@example.com", str(summary))
        self.assertNotIn("secret", str(summary))

    def test_rejects_tampered_signature(self) -> None:
        self.assertFalse(verify_callback(b"{}", "secret", "0" * 32))

    def test_replay_records_idempotency_without_storing_payload(self) -> None:
        body = b'{"syssn":"123","out_trade_no":"order-1","extra":"accepted"}'
        key = "secret"
        signature = hashlib.md5(body + key.encode()).hexdigest().upper()
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory) / "events.sqlite"
            self.assertTrue(replay_callback(body, key, signature, store)["accepted"])
            self.assertFalse(replay_callback(body, key, signature, store)["accepted"])
            self.assertNotIn(b"accepted", store.read_bytes())


if __name__ == "__main__":
    unittest.main()
