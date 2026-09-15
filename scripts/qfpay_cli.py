#!/usr/bin/env python3
"""QFPay developer CLI: offline docs, setup, validation, tests, and local read-only MCP."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

from qfpay_callback import callback_summary, listen_callbacks, replay_callback
from qfpay_sign import make_signature


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "references"
TEMPLATES = ROOT / "templates"
VERSION = "0.2.0"
REFERENCE_FILES = {
    "en": REFERENCES / "qfpay-openapi-reference.md",
    "zh-Hant": REFERENCES / "qfpay-openapi-reference.zh-Hant.md",
    "zh-CN": REFERENCES / "qfpay-openapi-reference.zh-CN.md",
}
AGENT_HOSTS = {
    "codex": ".codex",
    "claude-code": ".claude",
    "cursor": ".cursor",
}


def emit(data: object, as_json: bool = False) -> None:
    if as_json or isinstance(data, (dict, list)):
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(data)


def contract_summary() -> dict:
    manifest = json.loads((REFERENCES / "contract-manifest.json").read_text(encoding="utf-8"))
    contract = manifest["canonical_contract"]
    return {"version": contract["version"], "published_at": contract["published_at"], "url": contract["url"]}


def search_reference(source: Path, query: str, limit: int = 10) -> list[dict]:
    terms = [term.lower() for term in query.split() if term]
    matches = []
    for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if all(term in line.lower() for term in terms):
            matches.append({"line": number, "text": line.strip()[:300]})
            if len(matches) == limit:
                break
    return matches


def docs(args: argparse.Namespace) -> int:
    source = REFERENCE_FILES[args.locale]
    def find(query: str) -> tuple[Path, list[dict]]:
        matches = search_reference(source, query, args.limit)
        if not matches and source != REFERENCE_FILES["en"]:
            fallback = REFERENCE_FILES["en"]
            matches = search_reference(fallback, query, args.limit)
            return fallback, matches
        return source, matches

    lookup = args.lookup
    if lookup[0] == "search":
        if len(lookup) == 1:
            raise SystemExit("qfpay docs search requires a query")
        query = " ".join(lookup[1:])
        used_source, matches = find(query)
        emit({"source": used_source.name, "contract": contract_summary(), "query": query, "matches": matches}, args.json)
        return 0
    if lookup[0] == "api":
        if len(lookup) != 3:
            raise SystemExit("use: qfpay docs api METHOD /path")
        query = f"{lookup[1].upper()} {lookup[2]}"
        used_source, matches = find(lookup[2])
        emit({"source": used_source.name, "contract": contract_summary(), "query": query, "matches": matches}, args.json)
        return 0 if matches else 1
    path = " ".join(lookup)
    query = path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
    used_source, matches = find(query)
    emit({"source": used_source.name, "contract": contract_summary(), "path": path, "matches": matches}, args.json)
    return 0 if matches else 1


def local_mcp_config() -> dict:
    """Return a secret-free MCP fragment; callers choose the host-specific config location."""
    return {
        "mcpServers": {
            "qfpay-readonly": {
                "command": "qfpay",
                "args": ["mcp", "serve"],
                "env": {"QFPAY_ENV": "qa", "QFPAY_MCP_ALLOW_QUERY": "0"},
            }
        }
    }


def detect_agents() -> list[str]:
    return [name for name, directory in AGENT_HOSTS.items() if (Path.home() / directory).is_dir()]


def agent_setup(args: argparse.Namespace) -> int:
    detected = detect_agents()
    selected = (detected or list(AGENT_HOSTS)) if args.agent == "auto" else [args.agent]
    config = {
        "schema": "local stdio MCP configuration fragment",
        "target_agents": selected,
        "detected_agent_hosts": detected,
        "configuration": local_mcp_config(),
        "install_note": "Copy this secret-free fragment into the current MCP configuration location documented by the selected host. This command never writes host configuration.",
        "security_note": "Do not add QFPAY_CLIENT_KEY, app code, merchant IDs, or store IDs to agent configuration. The bundled MCP is documentation-first and read-only; a policy-controlled credential broker is required before enabling live enquiry.",
    }
    emit(config, True)
    return 0


def agent_doctor(args: argparse.Namespace) -> int:
    expected = [ROOT / "package.json", ROOT / ".codex-plugin" / "plugin.json", REFERENCES / "contract-manifest.json"]
    expected.extend(ROOT / "skills" / name / "SKILL.md" for name in skill_names())
    missing = [str(path.relative_to(ROOT)) for path in expected if not path.is_file()]
    result = {
        "version": VERSION,
        "contract": contract_summary(),
        "skills": skill_names(),
        "mcp": "local stdio, read-only, QA/Sandbox default; no Remote MCP",
        "detected_agent_hosts": detect_agents(),
        "missing": missing,
        "ready": not missing,
    }
    emit(result, True)
    return 0 if not missing else 1


def skill_names() -> list[str]:
    index = json.loads((ROOT / ".well-known" / "skills" / "index.json").read_text(encoding="utf-8"))
    return [skill["name"] for skill in index["skills"]]


def lint(args: argparse.Namespace) -> int:
    target = Path(args.path).resolve()
    if not target.exists():
        raise SystemExit(f"path does not exist: {target}")
    findings = []
    credential = re.compile(r"(?i)(client_key|qfpay_client_key)\s*[:=]\s*[\"'][^\"']+")
    old_url = re.compile(r"https://api\.qfapi\.com")
    web_suffixes = {".html", ".js", ".jsx", ".ts", ".tsx", ".vue"}
    source_suffixes = web_suffixes | {".py", ".env"}
    ignored = {".git", "node_modules", ".venv", "venv", "__pycache__"}
    files = [target] if target.is_file() else [path for path in target.rglob("*") if path.is_file() and not any(part in ignored for part in path.parts)]
    for path in files:
        if path.suffix.lower() not in source_suffixes:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        lower_parts = {part.lower() for part in path.parts}
        is_frontend = path.suffix.lower() == ".html" or bool({"client", "frontend", "public"} & lower_parts) or any(
            re.search(r"\b(window|document)\.", line) for line in lines
        )
        for number, line in enumerate(lines, start=1):
            if path.name != ".env.example" and credential.search(line):
                findings.append({"file": str(path), "line": number, "rule": "secret-in-source", "message": "Do not place client_key in source; use a server-side secret manager."})
            if old_url.search(line):
                findings.append({"file": str(path), "line": number, "rule": "unsupported-base-url", "message": "Use a documented QFPay environment URL from the versioned contract."})
            if is_frontend and "client_key" in line.lower():
                findings.append({"file": str(path), "line": number, "rule": "client-key-in-frontend", "message": "client_key must never reach frontend or mobile code."})
    emit({"path": str(target), "findings": findings, "passed": not findings}, True)
    return 0 if not findings else 1


def signature_test(args: argparse.Namespace) -> int:
    vectors = json.loads((ROOT / "tests" / "fixtures" / "signature-vectors.json").read_text(encoding="utf-8"))
    failures = []
    for vector in vectors:
        actual = make_signature(vector["params"], vector["client_key"], vector["sign_type"])
        if actual != vector["expected"]:
            failures.append(vector["name"])
    emit({"vectors": len(vectors), "failed": failures, "passed": not failures}, True)
    return 0 if not failures else 1


def evals_test(_: argparse.Namespace) -> int:
    import subprocess

    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_evals.py")], cwd=ROOT, check=False)
    return result.returncode


def callback_verify(args: argparse.Namespace) -> int:
    client_key = os.getenv("QFPAY_CLIENT_KEY")
    if args.prompt_client_key:
        import getpass

        client_key = getpass.getpass("QFPAY_CLIENT_KEY: ")
    if not client_key:
        raise SystemExit("client key is required via QFPAY_CLIENT_KEY or --prompt-client-key; it is never accepted as a command-line value")
    emit(callback_summary(Path(args.body_file).read_bytes(), client_key, args.signature), True)
    return 0


def callback_replay(args: argparse.Namespace) -> int:
    client_key = os.getenv("QFPAY_CLIENT_KEY")
    if args.prompt_client_key:
        import getpass

        client_key = getpass.getpass("QFPAY_CLIENT_KEY: ")
    if not client_key:
        raise SystemExit("client key is required via QFPAY_CLIENT_KEY or --prompt-client-key; it is never accepted as a command-line value")
    emit(replay_callback(Path(args.body_file).read_bytes(), client_key, args.signature, Path(args.store)), True)
    return 0


def callback_listen(args: argparse.Namespace) -> int:
    if os.getenv("QFPAY_ENV", "qa").lower() not in {"qa", "sandbox"}:
        raise SystemExit("the bundled callback listener is Sandbox-only; use a policy-controlled service for non-QA environments")
    client_key = os.getenv("QFPAY_CLIENT_KEY")
    if args.prompt_client_key:
        import getpass

        client_key = getpass.getpass("QFPAY_CLIENT_KEY: ")
    if not client_key:
        raise SystemExit("client key is required via QFPAY_CLIENT_KEY or --prompt-client-key; it is never accepted as a command-line value")
    listen_callbacks(client_key, args.port, Path(args.store))
    return 0


def init_template(args: argparse.Namespace) -> int:
    source = TEMPLATES / f"{args.integration}-{args.language}"
    if not source.is_dir():
        raise SystemExit(f"template is not available: {args.integration} for {args.language}")
    target = Path(args.output).resolve()
    if target.exists() and any(target.iterdir()) and not args.force:
        raise SystemExit("output directory is not empty; choose an empty directory or pass --force")
    target.mkdir(parents=True, exist_ok=True)
    for path in source.rglob("*"):
        destination = target / path.relative_to(source)
        if path.is_dir():
            destination.mkdir(exist_ok=True)
        else:
            if destination.exists() and not args.force:
                raise SystemExit(f"refusing to overwrite {destination}; pass --force to replace template files")
            shutil.copy2(path, destination)
    emit({"template": args.integration, "language": args.language, "output": str(target), "environment": "qa", "next_step": "Set server-only QA credentials locally, run qfpay lint, then execute the Sandbox tests."}, True)
    return 0


def mcp_serve(_: argparse.Namespace) -> int:
    from qfpay_mcp_server import serve

    serve()
    return 0


def transaction_get(args: argparse.Namespace) -> int:
    from qfpay_mcp_server import handle_tool_call

    arguments = {name: value for name, value in {"syssn": args.syssn, "out_trade_no": args.out_trade_no}.items() if value}
    if args.live_query:
        arguments["live_query"] = True
    result = handle_tool_call({"name": "qfpay_transaction_get", "arguments": arguments})
    emit(result["structuredContent"], True)
    return 1 if result["isError"] else 0


def paytypes(args: argparse.Namespace) -> int:
    from qfpay_mcp_server import handle_tool_call

    arguments = {name: value for name, value in {"channel": args.channel, "pay_type": args.pay_type}.items() if value}
    result = handle_tool_call({"name": "qfpay_paytypes", "arguments": arguments})
    emit(result["structuredContent"], True)
    return 1 if result["isError"] else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qfpay", description=__doc__)
    parser.add_argument("--version", action="version", version=f"qfpay {VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    docs_parser = subparsers.add_parser("docs", help="Read the bundled QFPay documentation snapshot")
    docs_parser.add_argument("--locale", choices=sorted(REFERENCE_FILES), default="zh-Hant")
    docs_parser.add_argument("--json", action="store_true")
    docs_parser.add_argument("--limit", type=int, default=10)
    docs_parser.add_argument("lookup", nargs="+", help="a docs path, or `search QUERY`, or `api METHOD /path`")

    agent_parser = subparsers.add_parser("agent", help="Set up or diagnose local agent integration")
    agent_sub = agent_parser.add_subparsers(dest="agent_command", required=True)
    setup_parser = agent_sub.add_parser("setup")
    setup_parser.add_argument("--agent", choices=["auto", *AGENT_HOSTS], default="auto")
    agent_sub.add_parser("doctor")

    init_parser = subparsers.add_parser("init", help="Copy a Sandbox integration template")
    init_parser.add_argument("integration", choices=["hosted-checkout", "mpm"])
    init_parser.add_argument("--language", choices=["node"], default="node")
    init_parser.add_argument("--output", default=".")
    init_parser.add_argument("--force", action="store_true")

    lint_parser = subparsers.add_parser("lint", help="Find QFPay secret and endpoint mistakes")
    lint_parser.add_argument("path", nargs="?", default=".")

    test_parser = subparsers.add_parser("test", help="Run deterministic QFPay checks")
    test_sub = test_parser.add_subparsers(dest="test_command", required=True)
    test_sub.add_parser("signature")
    test_sub.add_parser("evals")

    callback_parser = subparsers.add_parser("callback", help="Verify a raw QFPay callback")
    callback_sub = callback_parser.add_subparsers(dest="callback_command", required=True)
    callback_verify_parser = callback_sub.add_parser("verify")
    callback_verify_parser.add_argument("--body-file", required=True)
    callback_verify_parser.add_argument("--signature", required=True)
    callback_verify_parser.add_argument("--prompt-client-key", action="store_true")
    callback_replay_parser = callback_sub.add_parser("replay")
    callback_replay_parser.add_argument("--body-file", required=True)
    callback_replay_parser.add_argument("--signature", required=True)
    callback_replay_parser.add_argument("--store", default=".qfpay/callback-events.sqlite")
    callback_replay_parser.add_argument("--prompt-client-key", action="store_true")
    callback_listen_parser = callback_sub.add_parser("listen")
    callback_listen_parser.add_argument("--port", type=int, default=3001)
    callback_listen_parser.add_argument("--store", default=".qfpay/callback-events.sqlite")
    callback_listen_parser.add_argument("--prompt-client-key", action="store_true")

    mcp_parser = subparsers.add_parser("mcp", help="Run the local read-only stdio MCP")
    mcp_sub = mcp_parser.add_subparsers(dest="mcp_command", required=True)
    mcp_sub.add_parser("serve")

    transaction_parser = subparsers.add_parser("transaction", help="Perform a safe local Transaction Enquiry")
    transaction_sub = transaction_parser.add_subparsers(dest="transaction_command", required=True)
    transaction_get_parser = transaction_sub.add_parser("get")
    transaction_get_parser.add_argument("--syssn")
    transaction_get_parser.add_argument("--out-trade-no")
    transaction_get_parser.add_argument("--live-query", action="store_true", help="Only runs when the MCP host explicitly enables its bound QA read scope")

    paytypes_parser = subparsers.add_parser("paytypes", help="List documented pay_type values")
    paytypes_parser.add_argument("--channel")
    paytypes_parser.add_argument("--pay-type")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "docs":
        return docs(args)
    if args.command == "agent":
        return agent_setup(args) if args.agent_command == "setup" else agent_doctor(args)
    if args.command == "init":
        return init_template(args)
    if args.command == "lint":
        return lint(args)
    if args.command == "test":
        return signature_test(args) if args.test_command == "signature" else evals_test(args)
    if args.command == "callback":
        if args.callback_command == "verify":
            return callback_verify(args)
        if args.callback_command == "replay":
            return callback_replay(args)
        return callback_listen(args)
    if args.command == "mcp":
        return mcp_serve(args)
    if args.command == "transaction":
        return transaction_get(args)
    if args.command == "paytypes":
        return paytypes(args)
    raise AssertionError("unreachable")


if __name__ == "__main__":
    sys.exit(main())
