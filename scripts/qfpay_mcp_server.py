#!/usr/bin/env python3
"""A local, read-only stdio MCP server for QFPay documentation and enquiry.

This server deliberately does not expose payment creation, checkout signing, refunds, or
other money-moving tools.  It is not a Remote MCP implementation and must not be exposed
on an HTTP port.  Credentials, if local transaction enquiry is enabled, are read only from
the MCP host environment and are never accepted from, or returned to, the model.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import sys
import traceback
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from qfpay_sign import ENVIRONMENTS, make_signature


PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "qfpay-openapi-readonly"
SERVER_VERSION = "0.2.0"
ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = ROOT / "references"
ENV_ALIASES = {
    "sandbox": "qa",
    "qa": "qa",
    "test": "live-testing",
    "live-testing": "live-testing",
    "gray": "gray",
    "grey": "gray",
    "production": "production",
    "prod": "production",
}
SENSITIVE_KEY_PARTS = (
    "appcode",
    "app_code",
    "auth",
    "buyer",
    "card",
    "client_key",
    "email",
    "idnumber",
    "id_no",
    "mchid",
    "mchntid",
    "mobile",
    "openid",
    "phone",
    "secret",
    "signature",
    "sign",
    "token",
)


def object_schema(properties: dict, required: tuple[str, ...] = ()) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


TOOLS = [
    {
        "name": "qfpay_docs_search",
        "title": "QFPay Documentation Search",
        "description": "Search the bundled, versioned QFPay documentation snapshot. This tool never makes a network request.",
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "inputSchema": object_schema(
            {
                "query": {"type": "string", "minLength": 2, "maxLength": 120},
                "locale": {"type": "string", "enum": ["en", "zh-Hant", "zh-CN"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            ("query",),
        ),
    },
    {
        "name": "qfpay_paytypes",
        "title": "QFPay Pay Types",
        "description": "List documented QFPay pay_type values from the bundled documentation snapshot.",
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "inputSchema": object_schema(
            {
                "channel": {"type": "string", "maxLength": 80},
                "pay_type": {"type": "string", "pattern": "^[0-9]{6}$"},
            }
        ),
    },
    {
        "name": "qfpay_transaction_get",
        "title": "QFPay Transaction Enquiry",
        "description": "Preview or, when the local host explicitly enables it, query one transaction. The environment and credentials are fixed by the MCP host; the model cannot supply either.",
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "inputSchema": object_schema(
            {
                "syssn": {"type": "string", "minLength": 1, "maxLength": 128},
                "out_trade_no": {"type": "string", "minLength": 1, "maxLength": 128},
                "live_query": {"type": "boolean", "default": False},
            }
        ),
    },
]


def validate_schema(value: object, schema: dict, path: str = "arguments") -> None:
    """Validate the limited JSON Schema subset used by this server at its trust boundary."""
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(value, dict):
            raise ValueError(f"{path} must be an object")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(value) - set(properties))
            if unknown:
                raise ValueError(f"{path} contains unsupported field(s): {', '.join(unknown)}")
        missing = [field for field in schema.get("required", []) if field not in value]
        if missing:
            raise ValueError(f"{path} is missing required field(s): {', '.join(missing)}")
        for key, child in value.items():
            validate_schema(child, properties[key], f"{path}.{key}")
        return
    if expected == "string":
        if not isinstance(value, str):
            raise ValueError(f"{path} must be a string")
        if len(value) < schema.get("minLength", 0):
            raise ValueError(f"{path} is too short")
        if len(value) > schema.get("maxLength", 2**31):
            raise ValueError(f"{path} is too long")
        pattern = schema.get("pattern")
        if pattern and re.fullmatch(pattern, value) is None:
            raise ValueError(f"{path} has an invalid format")
    elif expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{path} must be an integer")
        if value < schema.get("minimum", -(2**63)) or value > schema.get("maximum", 2**63 - 1):
            raise ValueError(f"{path} is outside its allowed range")
    elif expected == "boolean" and not isinstance(value, bool):
        raise ValueError(f"{path} must be a boolean")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} must be one of: {', '.join(map(str, schema['enum']))}")


def mask(value: object, visible: int = 4) -> str:
    text = "" if value is None else str(value)
    if len(text) <= visible * 2:
        return "<redacted>"
    return f"{text[:visible]}...{text[-visible:]}"


def redact(value: object, key: str = "") -> object:
    """Redact structured and textual tool results before either MCP representation is made."""
    lowered = key.lower()
    if any(part in lowered for part in SENSITIVE_KEY_PARTS):
        return "<redacted>"
    if isinstance(value, dict):
        return {str(child_key): redact(child_value, str(child_key)) for child_key, child_value in value.items()}
    if isinstance(value, list):
        return [redact(item, key) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)(appcode|app_code|sign|signature|token)=([^&\s]+)", r"\1=<redacted>", value)
    return value


def reference_file(locale: str | None) -> Path:
    names = {
        "en": "qfpay-openapi-reference.md",
        "zh-Hant": "qfpay-openapi-reference.zh-Hant.md",
        "zh-CN": "qfpay-openapi-reference.zh-CN.md",
    }
    return REFERENCE_ROOT / names.get(locale or "zh-Hant", names["zh-Hant"])


def docs_search(args: dict) -> dict:
    source = reference_file(args.get("locale"))
    query_terms = [term.lower() for term in args["query"].split() if term]
    limit = args.get("limit", 5)
    matches = []
    for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if all(term in line.lower() for term in query_terms):
            matches.append({"line": number, "text": line.strip()[:300]})
            if len(matches) >= limit:
                break
    return {
        "source": source.name,
        "contract": contract_summary(),
        "query": args["query"],
        "count": len(matches),
        "matches": matches,
    }


def read_paytypes() -> list[dict]:
    path = REFERENCE_ROOT / "qfpay-openapi-reference.zh-CN.md"
    rows = []
    in_section = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## 完整 pay_type 清单"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4 or cells[1] in {"pay_type", "---"} or not cells[1].startswith("`"):
            continue
        rows.append({"channel": cells[0], "pay_type": cells[1].strip("`"), "scenario": cells[2], "entry": cells[3]})
    return rows


def paytypes(args: dict) -> dict:
    rows = read_paytypes()
    if args.get("channel"):
        channel = args["channel"].lower()
        rows = [row for row in rows if channel in row["channel"].lower()]
    if args.get("pay_type"):
        rows = [row for row in rows if row["pay_type"] == args["pay_type"]]
    return {"contract": contract_summary(), "count": len(rows), "paytypes": rows}


def host_environment() -> str:
    raw = os.getenv("QFPAY_ENV", "qa").strip().lower()
    if raw not in ENV_ALIASES:
        raise ValueError("MCP host has an unsupported QFPAY_ENV")
    env = ENV_ALIASES[raw]
    if env != "qa" and os.getenv("QFPAY_MCP_ALLOW_NON_QA") != "1":
        raise ValueError("this MCP is QA/Sandbox-only; configure a policy-controlled gateway for non-QA access")
    return env


def request_identifier(args: dict) -> tuple[str, str]:
    identifiers = [(name, args[name]) for name in ("syssn", "out_trade_no") if args.get(name)]
    if len(identifiers) != 1:
        raise ValueError("provide exactly one of syssn or out_trade_no")
    return identifiers[0]


def transaction_get(args: dict) -> dict:
    name, identifier = request_identifier(args)
    env = host_environment()
    trace_id = hashlib.sha256(f"{env}:{name}:{identifier}".encode("utf-8")).hexdigest()[:16]
    preview = {
        "trace_id": trace_id,
        "environment": env,
        "operation": "transaction_enquiry",
        "identifier": {name: mask(identifier)},
        "request_path": "/trade/v1/query",
        "state": "ACTION_REQUIRED",
        "next_step": "Enable a host-controlled QA read scope to run the enquiry; do not create a new order while status is unknown.",
    }
    if not args.get("live_query"):
        return preview
    if os.getenv("QFPAY_MCP_ALLOW_QUERY") != "1":
        preview["next_step"] = "The MCP host has not granted query access. Set QFPAY_MCP_ALLOW_QUERY=1 only for the bound QA profile."
        return preview
    response = send_query(env, {name: identifier})
    return {**preview, **response, "live_query": True}


def send_query(env: str, params: dict[str, str]) -> dict:
    """Perform only a server-side, host-authorized transaction enquiry."""
    app_code = os.getenv("QFPAY_APP_CODE")
    client_key = os.getenv("QFPAY_CLIENT_KEY")
    if not app_code or not client_key:
        raise ValueError("the MCP host needs its bound QFPAY_APP_CODE and QFPAY_CLIENT_KEY to perform an enquiry")
    sign_type = os.getenv("QFPAY_SIGN_TYPE", "MD5").upper()
    if sign_type not in {"MD5", "SHA256"}:
        raise ValueError("MCP host has an unsupported QFPAY_SIGN_TYPE")
    signature = make_signature(params, client_key, sign_type)
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-QF-APPCODE": app_code,
        "X-QF-SIGN": signature,
    }
    if sign_type == "SHA256":
        headers["X-QF-SIGNTYPE"] = "SHA256"
    request = Request(
        ENVIRONMENTS[env].rstrip("/") + "/trade/v1/query",
        data=urlencode(sorted(params.items())).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=30, context=ssl_context()) as handle:
            body = handle.read().decode("utf-8", errors="replace")
            return normalize_query_response(handle.status, body)
    except HTTPError as exc:
        return normalize_query_response(exc.code, exc.read().decode("utf-8", errors="replace"))
    except (URLError, TimeoutError) as exc:
        return {
            "http_status": None,
            "state": "UNKNOWN",
            "recovery": "Keep the same identifier and perform Transaction Enquiry again. Do not retry payment, refund, or fulfilment.",
            "error_class": type(exc).__name__,
        }


def ssl_context():
    cafile = os.getenv("QFPAY_CA_BUNDLE")
    if not cafile:
        try:
            import certifi

            cafile = certifi.where()
        except ImportError:
            cafile = None
    return ssl.create_default_context(cafile=cafile)


def normalize_query_response(http_status: int, body: str) -> dict:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    code = str(parsed.get("respcd", ""))
    state = normalize_state(code, parsed)
    allowed = {"respcd", "resperr", "status", "txamt", "txcurrcd", "syssn", "out_trade_no", "origssn", "orig_syssn"}
    details = {key: parsed[key] for key in allowed if key in parsed}
    return {
        "http_status": http_status,
        "state": state,
        "transaction": redact(details),
        "recovery": recovery_for(state),
    }


def normalize_state(code: str, payload: dict) -> str:
    if code in {"1143", "1145"}:
        return "PROCESSING"
    if code == "1298" or not code:
        return "UNKNOWN"
    if code != "0000":
        return "FAILED"
    status = str(payload.get("status", payload.get("trade_state", ""))).lower()
    if status in {"1", "success", "succeeded", "paid"}:
        return "SUCCESS"
    if status in {"0", "failed", "failure", "closed", "cancelled"}:
        return "FAILED"
    return "ACTION_REQUIRED"


def recovery_for(state: str) -> str:
    if state == "SUCCESS":
        return "Confirm the verified callback and merchant fulfilment rules before fulfilment."
    if state == "FAILED":
        return "Reconcile the original transaction before any new business decision."
    if state == "PROCESSING":
        return "Wait, then perform Transaction Enquiry with the same identifier; do not issue a new order."
    if state == "UNKNOWN":
        return "Do not retry payment, refund, or fulfilment. Perform Transaction Enquiry using the same identifier."
    return "The response does not establish a final transaction state. Use a verified callback plus Transaction Enquiry."


def contract_summary() -> dict:
    manifest_path = REFERENCE_ROOT / "contract-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = manifest["canonical_contract"]
    return {"version": contract["version"], "published_at": contract["published_at"], "source": contract["url"]}


TOOL_HANDLERS = {
    "qfpay_docs_search": docs_search,
    "qfpay_paytypes": paytypes,
    "qfpay_transaction_get": transaction_get,
}
TOOL_SCHEMAS = {tool["name"]: tool["inputSchema"] for tool in TOOLS}


def mcp_result(data: dict, is_error: bool = False) -> dict:
    safe = redact(data)
    return {
        "content": [{"type": "text", "text": json.dumps(safe, ensure_ascii=False, indent=2)}],
        "structuredContent": safe,
        "isError": is_error,
    }


def initialize_result(params: dict | None) -> dict:
    requested = (params or {}).get("protocolVersion") or PROTOCOL_VERSION
    protocol = requested if requested in {"2024-11-05", "2025-03-26", "2025-06-18"} else PROTOCOL_VERSION
    return {
        "protocolVersion": protocol,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": SERVER_NAME, "title": "QFPay Read-only Local MCP", "version": SERVER_VERSION},
        "instructions": "This is a local stdio, read-only MCP. It never accepts credentials, merchant/store selection, payment creation, checkout signing, refunds, or other funds actions. QA is the default environment. A Remote MCP requires OAuth, merchant/store scopes, Vault/KMS, approval, audit, and rate-limit controls that are not implemented here.",
    }


def handle_tool_call(params: dict | None) -> dict:
    name = (params or {}).get("name")
    args = (params or {}).get("arguments") or {}
    if name not in TOOL_HANDLERS:
        raise KeyError(f"unknown tool: {name}")
    try:
        validate_schema(args, TOOL_SCHEMAS[name])
        return mcp_result(TOOL_HANDLERS[name](args))
    except Exception as exc:
        return mcp_result({"error": str(exc)}, True)


def handle_request(message: object) -> dict | None:
    if not isinstance(message, dict):
        return error_response(None, -32600, "invalid request")
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params")
    notification = "id" not in message
    try:
        if method == "initialize":
            result = initialize_result(params if isinstance(params, dict) else None)
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            result = handle_tool_call(params if isinstance(params, dict) else None)
        elif method in {"notifications/initialized", "notifications/cancelled"}:
            return None
        else:
            return None if notification else error_response(msg_id, -32601, f"method not found: {method}")
    except KeyError as exc:
        return error_response(msg_id, -32602, str(exc))
    except Exception as exc:
        return error_response(msg_id, -32603, str(exc), {"trace": traceback.format_exc()})
    return None if notification else {"jsonrpc": "2.0", "id": msg_id, "result": result}


def error_response(msg_id: object, code: int, message: str, data: dict | None = None) -> dict:
    error = {"code": code, "message": message}
    if data and os.getenv("QFPAY_MCP_DEBUG") == "1":
        error["data"] = data
    return {"jsonrpc": "2.0", "id": msg_id, "error": error}


def write_message(message: object) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def serve() -> None:
    for line in sys.stdin:
        if not (line := line.strip()):
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            write_message(error_response(None, -32700, f"parse error: {exc}"))
            continue
        if isinstance(request, list):
            responses = [response for item in request if (response := handle_request(item)) is not None]
            if responses:
                write_message(responses)
            continue
        response = handle_request(request)
        if response is not None:
            write_message(response)


def self_test() -> None:
    tools = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {tool["name"] for tool in tools["result"]["tools"]}
    assert names == {"qfpay_docs_search", "qfpay_paytypes", "qfpay_transaction_get"}
    assert "qfpay_payment" not in names
    assert {row["pay_type"] for row in paytypes({"channel": "FPS"})["paytypes"]} == {"802001", "802010"}
    invalid = handle_tool_call({"name": "qfpay_transaction_get", "arguments": {"syssn": "1", "app_code": "LEAK"}})
    assert invalid["isError"] is True
    assert "LEAK" not in json.dumps(invalid)
    negative = handle_tool_call({"name": "qfpay_paytypes", "arguments": {"pay_type": "BAD"}})
    assert negative["isError"] is True
    preview = handle_tool_call({"name": "qfpay_transaction_get", "arguments": {"out_trade_no": "ORDER_1001"}})
    assert preview["isError"] is False
    assert preview["structuredContent"]["environment"] == "qa"
    print("read-only mcp server self-test ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        serve()
