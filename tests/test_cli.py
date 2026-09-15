from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "qfpay_cli.py"


class CliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(CLI), *args], cwd=ROOT, text=True, capture_output=True, check=False)

    def test_docs_direct_path_and_signature_vectors(self) -> None:
        docs = self.run_cli("docs", "/integration/common-api/transaction-enquiry")
        self.assertEqual(docs.returncode, 0, docs.stderr)
        self.assertIn("contract", docs.stdout)
        signature = self.run_cli("test", "signature")
        self.assertEqual(signature.returncode, 0, signature.stdout + signature.stderr)
        self.assertIn('"passed": true', signature.stdout)

    def test_doctor_and_safe_template_init(self) -> None:
        doctor = self.run_cli("agent", "doctor")
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
        agent_config = self.run_cli("agent", "setup", "--agent", "claude-code")
        self.assertEqual(agent_config.returncode, 0, agent_config.stdout + agent_config.stderr)
        self.assertIn('"claude-code"', agent_config.stdout)
        self.assertNotIn('"QFPAY_CLIENT_KEY":', agent_config.stdout)
        with tempfile.TemporaryDirectory() as directory:
            init = self.run_cli("init", "hosted-checkout", "--output", directory)
            self.assertEqual(init.returncode, 0, init.stdout + init.stderr)
            self.assertTrue((Path(directory) / "server.js").is_file())

    def test_lint_detects_a_frontend_secret_without_echoing_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = Path(directory) / "client.js"
            client.write_text('window.start = true;\nconst client_key = "do-not-leak";\n', encoding="utf-8")
            result = self.run_cli("lint", directory)
            self.assertEqual(result.returncode, 1)
            self.assertIn("client-key-in-frontend", result.stdout)
            self.assertNotIn("do-not-leak", result.stdout)

    def test_eval_contract_is_available_through_cli(self) -> None:
        result = self.run_cli("test", "evals")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("eval contract check ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
