from __future__ import annotations

import subprocess
import sys
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def run_script(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(ROOT / "scripts" / name), *args], cwd=ROOT, text=True, capture_output=True, check=False)

    def test_preview_release_evidence_is_current(self) -> None:
        manifest = self.run_script("build_release_manifest.py", "--check")
        self.assertEqual(manifest.returncode, 0, manifest.stdout + manifest.stderr)
        preview = self.run_script("check_public_release.py", "--preview")
        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)

    def test_public_gate_rejects_this_non_public_preview(self) -> None:
        result = self.run_script("check_public_release.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("private to false", result.stdout)
        self.assertIn("approved SPDX license", result.stdout)
        self.assertIn("canonical_contract.sha256", result.stdout)

    def test_npm_package_excludes_local_environment_files(self) -> None:
        with tempfile.TemporaryDirectory() as cache:
            environment = os.environ.copy()
            environment["npm_config_cache"] = cache
            result = subprocess.run(["npm", "pack", "--dry-run", "--json"], cwd=ROOT, text=True, capture_output=True, env=environment, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        paths = {item["path"] for item in json.loads(result.stdout)[0]["files"]}
        self.assertNotIn("templates/hosted-checkout-node/.env", paths)
        self.assertIn("templates/hosted-checkout-node/.env.example", paths)

    def test_hosted_checkout_template_redirects_without_returning_signed_url_json(self) -> None:
        source = (ROOT / "templates" / "hosted-checkout-node" / "server.js").read_text(encoding="utf-8")
        self.assertIn("response.writeHead(303", source)
        self.assertIn('"cache-control": "no-store"', source)
        self.assertNotIn("checkoutUrl:", source)


if __name__ == "__main__":
    unittest.main()
