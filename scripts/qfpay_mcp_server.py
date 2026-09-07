#!/usr/bin/env python3
"""stdio MCP server for QFPay OpenAPI transaction tools."""

import json
import os
import ssl
import sys
import traceback
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from qfpay_sign import (
    ENVIRONMENTS,
    build_url,
    canonical_string,
    display_params,
    encoded_params,
    make_signature,
    mask,
    stringify,
)


PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "qfpay-openapi-transactions"
SERVER_VERSION = "0.1.0"
MONEY_MUTATION_TOOLS = {
    "qfpay_refund",
    "qfpay_reversal",
    "qfpay_close",
    "qfpay_authtrade",
    "qfpay_unfreeze",
}
ENV_ALIASES = {
    "sandbox": "qa",
    "qa": "qa",
    "test": "live-testing",
    "live-testing": "live-testing",
    "production": "production",
    "prod": "production",
}


def schema(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required)}


COMMON_AUTH_FIELDS = {
    "env": {
        "type": "string",
        "enum": ["qa", "live-testing", "production"],
        "description": "QFPay environment. Defaults to QFPAY_ENV or live-testing.",
    },
    "app_code": {
        "type": "string",
        "description": "QFPay app code. Prefer QFPAY_APP_CODE environment variable.",
    },
    "client_key": {
        "type": "string",
        "description": "QFPay client key. Prefer QFPAY_CLIENT_KEY environment variable.",
    },
    "sign_type": {"type": "string", "enum": ["MD5", "SHA256"], "default": "MD5"},
    "execute": {
        "type": "boolean",
        "default": False,
        "description": "False returns a redacted signed preview. True sends the API request.",
    },
    "confirm_production": {
        "type": "boolean",
        "default": False,
        "description": "Required when execute=true and env=production.",
    },
}


COMMON_PAYMENT_FIELDS = {
    **COMMON_AUTH_FIELDS,
    "pay_type": {"type": "string", "description": "Six-digit QFPay pay_type."},
    "txamt": {"type": "integer", "minimum": 1, "description": "Amount in minor units, e.g. 100 = HKD 1.00."},
    "txcurrcd": {"type": "string", "default": "HKD"},
    "out_trade_no": {"type": "string"},
    "txdtm": {"type": "string", "description": "YYYY-MM-DD HH:mm:ss. Defaults to now."},
    "mchid": {"type": "string"},
    "auth_code": {"type": "string"},
    "sub_openid": {"type": "string"},
    "openid": {"type": "string"},
    "notify_url": {"type": "string"},
    "return_url": {"type": "string"},
    "failed_url": {"type": "string"},
    "goods_name": {"type": "string"},
    "expired_time": {"type": "string"},
    "pay_tag": {"type": "string"},
    "limit_pay": {"type": "string"},
    "udid": {"type": "string"},
    "extend_info": {"type": ["object", "string"]},
    "extra_params": {"type": "object", "description": "Additional QFPay form fields."},
}


TOOLS = [
    {
        "name": "qfpay_payment",
        "title": "QFPay Payment",
        "description": "Create MPM, CPM, Web, WAP/H5, In-App, FPS, wallet, or QR payment orders through /trade/v1/payment.",
        "inputSchema": schema(COMMON_PAYMENT_FIELDS, ["pay_type", "txamt", "out_trade_no"]),
    },
    {
        "name": "qfpay_query",
        "title": "QFPay Query",
        "description": "Query transaction status or order lists through /trade/v1/query.",
        "inputSchema": schema(
            {
                **COMMON_AUTH_FIELDS,
                "syssn": {"type": "string"},
                "out_trade_no": {"type": "string"},
                "pay_type": {"type": "string"},
                "respcd": {"type": "string"},
                "start_time": {"type": "string"},
                "end_time": {"type": "string"},
                "page": {"type": "integer", "minimum": 1},
                "page_size": {"type": "integer", "minimum": 1, "maximum": 100},
                "mchid": {"type": "string"},
                "extra_params": {"type": "object"},
            }
        ),
    },
    {
        "name": "qfpay_refund",
        "title": "QFPay Refund",
        "description": "Refund a successful payment through /trade/v1/refund. Requires confirm_funds_action=true when execute=true.",
        "inputSchema": schema(
            {
                **COMMON_AUTH_FIELDS,
                "confirm_funds_action": {"type": "boolean", "default": False},
                "syssn": {"type": "string", "description": "Original payment syssn."},
                "out_trade_no": {"type": "string", "description": "Unique merchant refund order number."},
                "txamt": {"type": "integer", "minimum": 1},
                "txdtm": {"type": "string", "description": "Defaults to now."},
                "mchid": {"type": "string"},
                "udid": {"type": "string"},
                "extra_params": {"type": "object"},
            },
            ["syssn", "out_trade_no", "txamt"],
        ),
    },
    {
        "name": "qfpay_reversal",
        "title": "QFPay Reversal",
        "description": "Reverse/void an unfinished QR or card authorization through /trade/v1/reversal. Requires confirm_funds_action=true when execute=true.",
        "inputSchema": schema(
            {
                **COMMON_AUTH_FIELDS,
                "confirm_funds_action": {"type": "boolean", "default": False},
                "syssn": {"type": "string"},
                "out_trade_no": {"type": "string"},
                "txamt": {"type": "integer", "minimum": 1},
                "txdtm": {"type": "string", "description": "Original transaction time."},
                "mchid": {"type": "string"},
                "udid": {"type": "string"},
                "extra_params": {"type": "object"},
            },
            ["txamt", "txdtm"],
        ),
    },
    {
        "name": "qfpay_close",
        "title": "QFPay Close",
        "description": "Close an order through GET /trade/v1/close. Requires confirm_funds_action=true when execute=true.",
        "inputSchema": schema(
            {
                **COMMON_AUTH_FIELDS,
                "confirm_funds_action": {"type": "boolean", "default": False},
                "syssn": {"type": "string"},
                "out_trade_no": {"type": "string"},
                "txamt": {"type": "integer", "minimum": 1},
                "txdtm": {"type": "string", "description": "Original transaction time."},
                "mchid": {"type": "string"},
                "udid": {"type": "string"},
                "extra_params": {"type": "object"},
            },
            ["txamt", "txdtm"],
        ),
    },
    {
        "name": "qfpay_authtrade",
        "title": "QFPay Preauth Capture",
        "description": "Capture a preauthorization through /trade/v1/authtrade. Requires confirm_funds_action=true when execute=true.",
        "inputSchema": schema(
            {
                **COMMON_AUTH_FIELDS,
                "confirm_funds_action": {"type": "boolean", "default": False},
                "syssn": {"type": "string"},
                "txamt": {"type": "integer", "minimum": 1},
                "txcurrcd": {"type": "string"},
                "mchid": {"type": "string"},
                "extra_params": {"type": "object"},
            },
            ["syssn", "txamt"],
        ),
    },
    {
        "name": "qfpay_unfreeze",
        "title": "QFPay Preauth Unfreeze",
        "description": "Unfreeze a preauthorization through /trade/v1/unfreeze. Requires confirm_funds_action=true when execute=true.",
        "inputSchema": schema(
            {
                **COMMON_AUTH_FIELDS,
                "confirm_funds_action": {"type": "boolean", "default": False},
                "syssn": {"type": "string"},
                "out_trade_no": {"type": "string"},
                "txamt": {"type": "integer", "minimum": 1},
                "txdtm": {"type": "string"},
                "mchid": {"type": "string"},
                "extra_params": {"type": "object"},
            },
            ["syssn", "out_trade_no", "txamt", "txdtm"],
        ),
    },
    {
        "name": "qfpay_payment_intent",
        "title": "QFPay Element Intent",
        "description": "Create a Payment Element intent through /payment_element/v1/create_payment_intent.",
        "inputSchema": schema(
            {
                **COMMON_PAYMENT_FIELDS,
                "failed_url": {"type": "string"},
            },
            ["txamt", "pay_type", "out_trade_no"],
        ),
    },
    {
        "name": "qfpay_checkout_url",
        "title": "QFPay Hosted Checkout URL",
        "description": "Generate a signed Hosted Checkout URL. This does not send a network request.",
        "inputSchema": schema(
            {
                "env": COMMON_AUTH_FIELDS["env"],
                "app_code": COMMON_AUTH_FIELDS["app_code"],
                "client_key": COMMON_AUTH_FIELDS["client_key"],
                "sign_type": {"type": "string", "enum": ["MD5", "SHA256"], "default": "SHA256"},
                "paysource": {"type": "string", "default": "remotepay_checkout"},
                "txamt": {"type": "integer", "minimum": 1},
                "txcurrcd": {"type": "string", "default": "HKD"},
                "out_trade_no": {"type": "string"},
                "txdtm": {"type": "string", "description": "Defaults to now."},
                "return_url": {"type": "string"},
                "failed_url": {"type": "string"},
                "notify_url": {"type": "string"},
                "mchntid": {"type": "string"},
                "goods_name": {"type": "string"},
                "udid": {"type": "string"},
                "expired_time": {"type": "string"},
                "checkout_expired_time": {"type": "string"},
                "limit_pay": {"type": "string"},
                "lang": {"type": "string"},
                "cancel_url": {"type": "string"},
                "extra_params": {"type": "object"},
            },
            ["txamt", "out_trade_no", "return_url", "failed_url", "notify_url"],
        ),
    },
    {
        "name": "qfpay_paytypes",
        "title": "QFPay Pay Types",
        "description": "List documented QFPay pay_type values from the bundled reference, optionally filtered by channel or pay_type.",
        "inputSchema": schema(
            {
                "channel": {"type": "string", "description": "Case-insensitive channel filter, e.g. FPS, Octopus, Alipay."},
                "pay_type": {"type": "string", "description": "Exact six-digit pay_type filter."},
            }
        ),
    },
]


def now_dtm():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def add_param(params, key, value):
    if value is None or value == "":
        return
    params[key] = stringify(value)


def add_fields(params, args, fields):
    for field in fields:
        add_param(params, field, args.get(field))


def build_params(args, fields, defaults=None):
    params = {}
    extra = args.get("extra_params") or {}
    if not isinstance(extra, dict):
        raise ValueError("extra_params must be an object")
    for key, value in extra.items():
        add_param(params, str(key), value)
    for key, value in (defaults or {}).items():
        add_param(params, key, args.get(key, value))
    add_fields(params, args, fields)
    return params


def normalize_env(raw):
    env = raw or os.getenv("QFPAY_ENV") or "live-testing"
    env = str(env).strip().lower()
    if env not in ENV_ALIASES:
        raise ValueError(f"unsupported env: {env}")
    return ENV_ALIASES[env]


def resolve_context(args):
    env = normalize_env(args.get("env"))
    app_code = args.get("app_code") or os.getenv("QFPAY_APP_CODE")
    client_key = args.get("client_key") or os.getenv("QFPAY_CLIENT_KEY")
    if not app_code:
        raise ValueError("app_code is required via tool argument or QFPAY_APP_CODE")
    if not client_key:
        raise ValueError("client_key is required via tool argument or QFPAY_CLIENT_KEY")
    return env, ENVIRONMENTS[env], str(app_code), str(client_key)


def check_execution_flags(tool_name, env, args):
    if not args.get("execute", False):
        return
    if env == "production" and not args.get("confirm_production", False):
        raise ValueError("confirm_production=true is required to execute against production")
    if tool_name in MONEY_MUTATION_TOOLS and not args.get("confirm_funds_action", False):
        raise ValueError("confirm_funds_action=true is required for this funds action")


def response_preview(env, base_url, path, method, sign_type, app_code, params, execute):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-QF-APPCODE": mask(app_code),
        "X-QF-SIGN": "<redacted-signature>",
    }
    if sign_type == "SHA256":
        headers["X-QF-SIGNTYPE"] = "SHA256"
    return {
        "environment": env,
        "base_url": base_url,
        "method": method,
        "path": path,
        "url": build_url(base_url, path),
        "execute": execute,
        "headers": headers,
        "params": display_params(params, False),
        "canonical_without_client_key": canonical_string(display_params(params, False)),
        "encoded_params": encoded_params(display_params(params, False)),
    }


def send_form_request(base_url, path, method, app_code, sign_type, signature, params):
    method = method.upper()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-QF-APPCODE": app_code,
        "X-QF-SIGN": signature,
    }
    if sign_type == "SHA256":
        headers["X-QF-SIGNTYPE"] = "SHA256"

    url = build_url(base_url, path)
    data = None
    if method == "GET":
        url = url + "?" + urlencode([(key, params[key]) for key in sorted(params)])
    else:
        data = urlencode([(key, params[key]) for key in sorted(params)]).encode("utf-8")

    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30, context=ssl_context()) as handle:
            status = handle.status
            body = handle.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8", errors="replace")
    except URLError as exc:
        raise ValueError(f"network error: {exc.reason}") from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        parsed = body
    return {"http_status": status, "body": redact(parsed)}


def ssl_context():
    cafile = os.getenv("QFPAY_CA_BUNDLE")
    if not cafile:
        try:
            import certifi

            cafile = certifi.where()
        except ImportError:
            cafile = None
    return ssl.create_default_context(cafile=cafile)


def signed_form_tool(tool_name, args, path, method, params):
    env, base_url, app_code, client_key = resolve_context(args)
    sign_type = str(args.get("sign_type") or "MD5").upper()
    if sign_type not in {"MD5", "SHA256"}:
        raise ValueError("sign_type must be MD5 or SHA256")
    execute = bool(args.get("execute", False))
    check_execution_flags(tool_name, env, args)
    signature = make_signature(params, client_key, sign_type)
    result = response_preview(env, base_url, path, method, sign_type, app_code, params, execute)
    if execute:
        result["response"] = send_form_request(base_url, path, method, app_code, sign_type, signature, params)
    return result


def require_any(args, names):
    if not any(args.get(name) for name in names):
        joined = " or ".join(names)
        raise ValueError(f"{joined} is required")


def require_fields(args, names):
    missing = [name for name in names if args.get(name) in (None, "")]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")


def tool_payment(args):
    require_fields(args, ["pay_type", "txamt", "out_trade_no"])
    params = build_params(
        args,
        [
            "pay_type",
            "txamt",
            "txcurrcd",
            "out_trade_no",
            "txdtm",
            "mchid",
            "auth_code",
            "sub_openid",
            "openid",
            "notify_url",
            "return_url",
            "goods_name",
            "expired_time",
            "pay_tag",
            "limit_pay",
            "udid",
            "extend_info",
        ],
        {"txcurrcd": "HKD", "txdtm": now_dtm()},
    )
    return signed_form_tool("qfpay_payment", args, "/trade/v1/payment", "POST", params)


def tool_query(args):
    if not (args.get("syssn") or args.get("out_trade_no") or (args.get("start_time") and args.get("end_time"))):
        raise ValueError("provide syssn, out_trade_no, or both start_time and end_time")
    params = build_params(
        args,
        ["syssn", "out_trade_no", "pay_type", "respcd", "start_time", "end_time", "page", "page_size", "mchid"],
    )
    return signed_form_tool("qfpay_query", args, "/trade/v1/query", "POST", params)


def tool_refund(args):
    require_fields(args, ["syssn", "out_trade_no", "txamt"])
    params = build_params(args, ["syssn", "out_trade_no", "txamt", "txdtm", "mchid", "udid"], {"txdtm": now_dtm()})
    return signed_form_tool("qfpay_refund", args, "/trade/v1/refund", "POST", params)


def tool_reversal(args):
    require_any(args, ["syssn", "out_trade_no"])
    require_fields(args, ["txamt", "txdtm"])
    params = build_params(args, ["syssn", "out_trade_no", "txamt", "txdtm", "mchid", "udid"])
    return signed_form_tool("qfpay_reversal", args, "/trade/v1/reversal", "POST", params)


def tool_close(args):
    require_any(args, ["syssn", "out_trade_no"])
    require_fields(args, ["txamt", "txdtm"])
    params = build_params(args, ["syssn", "out_trade_no", "txamt", "txdtm", "mchid", "udid"])
    return signed_form_tool("qfpay_close", args, "/trade/v1/close", "GET", params)


def tool_authtrade(args):
    require_fields(args, ["syssn", "txamt"])
    params = build_params(args, ["syssn", "txamt", "txcurrcd", "mchid"])
    return signed_form_tool("qfpay_authtrade", args, "/trade/v1/authtrade", "POST", params)


def tool_unfreeze(args):
    require_fields(args, ["syssn", "out_trade_no", "txamt", "txdtm"])
    params = build_params(args, ["syssn", "out_trade_no", "txamt", "txdtm", "mchid"])
    return signed_form_tool("qfpay_unfreeze", args, "/trade/v1/unfreeze", "POST", params)


def tool_payment_intent(args):
    require_fields(args, ["txamt", "pay_type", "out_trade_no"])
    params = build_params(
        args,
        ["txamt", "pay_type", "out_trade_no", "txcurrcd", "mchid", "return_url", "failed_url", "notify_url"],
        {"txcurrcd": "HKD"},
    )
    return signed_form_tool(
        "qfpay_payment_intent",
        args,
        "/payment_element/v1/create_payment_intent",
        "POST",
        params,
    )


def tool_checkout_url(args):
    require_fields(args, ["txamt", "out_trade_no", "return_url", "failed_url", "notify_url"])
    env, base_url, app_code, client_key = resolve_context(args)
    sign_type = str(args.get("sign_type") or "SHA256").upper()
    if sign_type not in {"MD5", "SHA256"}:
        raise ValueError("sign_type must be MD5 or SHA256")
    params = build_params(
        args,
        [
            "paysource",
            "txamt",
            "txcurrcd",
            "out_trade_no",
            "txdtm",
            "return_url",
            "failed_url",
            "notify_url",
            "mchntid",
            "goods_name",
            "udid",
            "expired_time",
            "checkout_expired_time",
            "limit_pay",
            "lang",
            "cancel_url",
        ],
        {
            "paysource": "remotepay_checkout",
            "txcurrcd": "HKD",
            "txdtm": now_dtm(),
        },
    )
    params["appcode"] = app_code
    params["sign_type"] = sign_type
    signature = make_signature(params, client_key, sign_type)
    ordered = [(key, params[key]) for key in sorted(params)]
    ordered.append(("sign", signature))
    return {
        "environment": env,
        "base_url": base_url,
        "url": build_url(base_url, "/checkstand/#/") + "?" + urlencode(ordered),
        "redaction_note": "The URL contains a signature and should be handled as sensitive payment data.",
        "params": display_params(params, False),
    }


def tool_paytypes(args):
    rows = read_paytypes()
    channel = str(args.get("channel") or "").lower()
    pay_type = str(args.get("pay_type") or "")
    if channel:
        rows = [row for row in rows if channel in row["channel"].lower()]
    if pay_type:
        rows = [row for row in rows if row["pay_type"] == pay_type]
    return {"count": len(rows), "paytypes": rows}


TOOL_HANDLERS = {
    "qfpay_payment": tool_payment,
    "qfpay_query": tool_query,
    "qfpay_refund": tool_refund,
    "qfpay_reversal": tool_reversal,
    "qfpay_close": tool_close,
    "qfpay_authtrade": tool_authtrade,
    "qfpay_unfreeze": tool_unfreeze,
    "qfpay_payment_intent": tool_payment_intent,
    "qfpay_checkout_url": tool_checkout_url,
    "qfpay_paytypes": tool_paytypes,
}


def read_paytypes():
    path = Path(__file__).resolve().parents[1] / "references/qfpay-openapi-reference.zh-CN.md"
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
        if len(cells) < 4 or cells[1] in {"pay_type", "---"}:
            continue
        if not cells[1].startswith("`"):
            continue
        rows.append(
            {
                "channel": cells[0],
                "pay_type": cells[1].strip("`"),
                "scenario": cells[2],
                "entry": cells[3],
            }
        )
    return rows


def redact(value):
    if isinstance(value, dict):
        out = {}
        for key, child in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in ("client_key", "secret", "token", "auth_code", "openid", "card")):
                out[key] = "<redacted>"
            elif lowered in {"sign", "signature", "x-qf-sign"}:
                out[key] = "<redacted-signature>"
            else:
                out[key] = redact(child)
        return out
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def mcp_result(data, is_error=False):
    return {
        "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}],
        "structuredContent": data,
        "isError": is_error,
    }


def initialize_result(params):
    requested = (params or {}).get("protocolVersion") or PROTOCOL_VERSION
    protocol = requested if requested in {"2024-11-05", "2025-03-26", "2025-06-18"} else PROTOCOL_VERSION
    return {
        "protocolVersion": protocol,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": SERVER_NAME, "title": "QFPay OpenAPI Transactions", "version": SERVER_VERSION},
        "instructions": (
            "Use execute=false for signed previews and execute=true to call QFPay. "
            "Credentials come from QFPAY_APP_CODE/QFPAY_CLIENT_KEY or tool arguments. "
            "Production execution requires confirm_production=true; refunds, reversals, close, "
            "authtrade, and unfreeze also require confirm_funds_action=true."
        ),
    }


def handle_tool_call(params):
    name = (params or {}).get("name")
    args = (params or {}).get("arguments") or {}
    if name not in TOOL_HANDLERS:
        raise KeyError(f"unknown tool: {name}")
    if not isinstance(args, dict):
        raise ValueError("tool arguments must be an object")
    try:
        return mcp_result(TOOL_HANDLERS[name](args))
    except Exception as exc:
        return mcp_result({"error": str(exc)}, True)


def handle_request(message):
    if not isinstance(message, dict):
        return error_response(None, -32600, "invalid request")
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params")
    is_notification = "id" not in message

    try:
        if method == "initialize":
            result = initialize_result(params)
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            result = handle_tool_call(params)
        elif method in {"notifications/initialized", "notifications/cancelled"}:
            return None
        else:
            return None if is_notification else error_response(msg_id, -32601, f"method not found: {method}")
    except KeyError as exc:
        return error_response(msg_id, -32602, str(exc))
    except Exception as exc:
        return error_response(msg_id, -32603, str(exc), {"trace": traceback.format_exc()})

    if is_notification:
        return None
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def error_response(msg_id, code, message, data=None):
    error = {"code": code, "message": message}
    if data and os.getenv("QFPAY_MCP_DEBUG") == "1":
        error["data"] = data
    return {"jsonrpc": "2.0", "id": msg_id, "error": error}


def serve():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            write_message(error_response(None, -32700, f"parse error: {exc}"))
            continue

        if isinstance(message, list):
            responses = [response for item in message if (response := handle_request(item)) is not None]
            if responses:
                write_message(responses)
            continue

        response = handle_request(message)
        if response is not None:
            write_message(response)


def write_message(message):
    sys.stdout.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def self_test():
    init = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
        }
    )
    assert init["result"]["capabilities"]["tools"] == {"listChanged": False}
    tools = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert any(tool["name"] == "qfpay_payment" for tool in tools["result"]["tools"])
    paytypes = TOOL_HANDLERS["qfpay_paytypes"]({"channel": "FPS"})
    assert {row["pay_type"] for row in paytypes["paytypes"]} == {"802001", "802010"}
    payment = TOOL_HANDLERS["qfpay_payment"](
        {
            "env": "qa",
            "app_code": "APP_CODE_FOR_TEST",
            "client_key": "CLIENT_KEY_FOR_TEST",
            "pay_type": "802001",
            "txamt": 100,
            "out_trade_no": "MCP_SELF_TEST",
        }
    )
    dumped = json.dumps(payment)
    assert "CLIENT_KEY_FOR_TEST" not in dumped
    assert payment["execute"] is False
    print("mcp server self-test ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        serve()
