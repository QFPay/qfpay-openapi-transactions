# Public-release procedure

`0.2.0` is an internal, Sandbox-first preview. It deliberately has `private: true` and `UNLICENSED`; it must not be pushed to a public npm registry or advertised as a Remote MCP / Production payment product.

Before making any release public, a release owner must complete every item below. The automated gate checks only objective repository evidence; it cannot replace QFPay legal, security, merchant, or change-approval processes.

## Required human decisions

1. Obtain written confirmation that QFPay owns or may redistribute every bundled document, `pay_type` table, template, and generated package file under the selected licence.
2. Select the approved SPDX licence and add its full text as `LICENSE`.
3. Set the official HTTPS homepage and source repository URL in `package.json`; do not substitute a personal or temporary URL.
4. Assign a release owner to review the contract diff, test evidence, release manifest, and registry publication.
5. Keep remote execution disabled unless the separate Remote MCP / Production gates in the root `README.md` are completed and approved.

## Reproducible technical gate

From a clean, reviewed Git tag, use a supported Node/npm and Python 3.10+ runtime:

```bash
python3 scripts/check_contract_freshness.py
python3 scripts/check_paytype_coverage.py
python3 scripts/check_skill_release.py
python3 scripts/check_evals.py
python3 scripts/qfpay_mcp_server.py --self-test
python3 -m unittest discover -s tests -v
python3 scripts/build_release_manifest.py
python3 scripts/build_release_manifest.py --check
python3 scripts/check_public_release.py --preview
npm pack --dry-run
```

Refresh `references/contract-manifest.json` only after an authorised reviewer has compared the published canonical OpenAPI document. Download it to a controlled local path and run `python3 scripts/verify_contract_source.py --from-file /path/to/openapi.json`; it must identify itself as QFPay before you record its exact SHA-256 in `canonical_contract.sha256` and set `source_verification.status` to `verified`. Update the bundled snapshot and evaluation cases when behaviour changes, then regenerate `release/manifest.json`. Never accept a document merely because it is served from a similarly named URL.

After the human decisions above are recorded in the organisation’s normal approval system, set the public metadata and run:

```bash
python3 scripts/check_public_release.py
```

That command intentionally fails for this preview until it has a non-private package, approved licence file, official URLs, an exact contract hash, changelog, and a clean Git worktree. A passing check still does not authorize Production payments or Remote MCP execution.

## Publishing boundaries

- Publish `.well-known/skills/index.json` only at an organisation-controlled HTTPS origin after its URLs and ownership are approved.
- Publish the package only from CI or a controlled release workstation; preserve the generated `release/manifest.json` with the release evidence.
- MCP configuration remains local stdio and read-only. Never put `QFPAY_CLIENT_KEY`, app code, merchant identifiers, or store identifiers in Agent configuration, prompts, MCP arguments, packages, logs, or release evidence.
