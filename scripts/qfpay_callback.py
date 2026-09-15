#!/usr/bin/env python3
"""Verify QFPay callback signatures without printing callback payloads or secrets."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import json
import os
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def verify_callback(raw_body: bytes, client_key: str, signature: str) -> bool:
    expected = hashlib.md5(raw_body + client_key.encode("utf-8")).hexdigest().upper()
    return hmac.compare_digest(expected, signature.strip().upper())


def callback_summary(raw_body: bytes, client_key: str, signature: str) -> dict:
    """Return a privacy-preserving verification result suitable for CLI and test use."""
    return {
        "valid": verify_callback(raw_body, client_key, signature),
        "event_fingerprint": hashlib.sha256(raw_body).hexdigest()[:24],
        "payload_bytes": len(raw_body),
        "next_step": "Process idempotently, tolerate unknown fields and out-of-order delivery, then use Transaction Enquiry before fulfilment." if verify_callback(raw_body, client_key, signature) else "Reject the callback without returning SUCCESS; do not trust or fulfil it.",
    }


def callback_event_key(raw_body: bytes) -> str:
    """Create a stable idempotency key without persisting payload fields or PII."""
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        payload = {}
    if isinstance(payload, dict) and payload.get("syssn") and payload.get("out_trade_no"):
        material = f"{payload['syssn']}:{payload['out_trade_no']}".encode("utf-8")
    else:
        material = raw_body
    return hashlib.sha256(material).hexdigest()


class CallbackStore:
    """Minimal local idempotency store; it intentionally never persists callback bodies."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS callback_events (event_key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, received_at TEXT NOT NULL)"
        )
        self.connection.commit()

    def record(self, raw_body: bytes) -> bool:
        event_key = callback_event_key(raw_body)
        fingerprint = hashlib.sha256(raw_body).hexdigest()[:24]
        cursor = self.connection.execute(
            "INSERT OR IGNORE INTO callback_events(event_key, fingerprint, received_at) VALUES (?, ?, datetime('now'))",
            (event_key, fingerprint),
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def close(self) -> None:
        self.connection.close()


def replay_callback(raw_body: bytes, client_key: str, signature: str, store_path: Path) -> dict:
    result = callback_summary(raw_body, client_key, signature)
    if result["valid"]:
        store = CallbackStore(store_path)
        try:
            result["accepted"] = store.record(raw_body)
        finally:
            store.close()
    return result


def listen_callbacks(client_key: str, port: int, store_path: Path) -> None:
    """Listen only on loopback for Sandbox callback development; never expose a public listener."""
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length < 1 or content_length > 1_048_576:
                self.send_response(413)
                self.end_headers()
                return
            raw_body = self.rfile.read(content_length)
            signature = self.headers.get("X-QF-SIGN", "")
            if not signature or not verify_callback(raw_body, client_key, signature):
                self.send_response(400)
                self.end_headers()
                return
            store = CallbackStore(store_path)
            try:
                accepted = store.record(raw_body)
            finally:
                store.close()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"SUCCESS")
            fingerprint = hashlib.sha256(raw_body).hexdigest()[:24]
            print(f"callback {'accepted' if accepted else 'duplicate'}: {fingerprint}", file=sys.stderr, flush=True)

        def log_message(self, *_: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"QFPay Sandbox callback listener on http://127.0.0.1:{port}/ (loopback only)", file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body-file", required=True, help="Raw callback body file. The file is never echoed.")
    parser.add_argument("--signature", required=True, help="X-QF-SIGN header value")
    parser.add_argument("--prompt-client-key", action="store_true", help="Read client_key without terminal echo")
    parser.add_argument("--json", action="store_true", help="Emit JSON (the default output is also JSON)")
    args = parser.parse_args()
    client_key = os.getenv("QFPAY_CLIENT_KEY")
    if args.prompt_client_key:
        client_key = getpass.getpass("QFPAY_CLIENT_KEY: ")
    if not client_key:
        raise SystemExit("client key is required via QFPAY_CLIENT_KEY or --prompt-client-key; it is never accepted as a command-line value")
    raw_body = Path(args.body_file).read_bytes()
    print(json.dumps(callback_summary(raw_body, client_key, args.signature), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
