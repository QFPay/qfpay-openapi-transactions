#!/usr/bin/env python3
"""Generate QFPay signatures and cURL snippets without sending requests."""

import argparse
import getpass
import hashlib
import json
import os
import shlex
import sys
from urllib.parse import urlencode


ENVIRONMENTS = {
    "qa": "https://openapi-int.qfapi.com",
    "sandbox": "https://openapi-int.qfapi.com",
    "live-testing": "https://test-openapi-hk.qfapi.com",
    "test": "https://test-openapi-hk.qfapi.com",
    "gray": "https://gray-openapi-hk.qfapi.com",
    "grey": "https://gray-openapi-hk.qfapi.com",
    "production": "https://openapi-hk.qfapi.com",
    "prod": "https://openapi-hk.qfapi.com",
}

MASKED_PARAM_NAMES = {"app_code", "appcode", "mchid", "mchntid"}
REDACTED_PARAM_NAMES = {
    "auth_code",
    "buyer_id",
    "client_key",
    "customer_id",
    "email",
    "id_no",
    "idnumber",
    "mobile",
    "openid",
    "phone",
    "sub_openid",
}


def mask(value, visible=4):
    text = "" if value is None else str(value)
    if len(text) <= visible * 2:
        return "<redacted>"
    return f"{text[:visible]}...{text[-visible:]}"


def is_redacted_param(name):
    lowered = name.lower()
    if lowered == "sign_type":
        return False
    return (
        lowered in REDACTED_PARAM_NAMES
        or "card" in lowered
        or "key" in lowered
        or "openid" in lowered
        or "secret" in lowered
        or "sign" in lowered
        or "token" in lowered
    )


def display_params(params, show_sensitive):
    if show_sensitive:
        return dict(params)

    display = {}
    for key, value in params.items():
        lowered = key.lower()
        if lowered in MASKED_PARAM_NAMES:
            display[key] = mask(value)
        elif is_redacted_param(key):
            display[key] = "<redacted>"
        else:
            display[key] = value
    return display


def parse_key_value(value):
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected KEY=VALUE")
    key, raw = value.split("=", 1)
    if not key:
        raise argparse.ArgumentTypeError("empty parameter name")
    return key, raw


def stringify(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def load_params(args):
    params = {}
    if args.params_json:
        source = args.params_json
        if source.startswith("@"):
            with open(source[1:], "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        else:
            loaded = json.loads(source)
        if not isinstance(loaded, dict):
            raise SystemExit("--params-json must be a JSON object")
        params.update({str(k): stringify(v) for k, v in loaded.items()})

    for key, value in args.param:
        params[key] = value

    if not args.keep_empty:
        params = {k: v for k, v in params.items() if v is not None and str(v) != ""}

    if args.mode == "checkout":
        if args.app_code and "appcode" not in params:
            params["appcode"] = args.app_code
        if args.sign_type and "sign_type" not in params:
            params["sign_type"] = args.sign_type.upper()

    return {k: stringify(v) for k, v in params.items()}


def canonical_string(params):
    return "&".join(f"{key}={params[key]}" for key in sorted(params))


def encoded_params(params):
    return urlencode([(key, params[key]) for key in sorted(params)])


def make_signature(params, client_key, sign_type):
    payload = (canonical_string(params) + client_key).encode("utf-8")
    if sign_type.upper() == "SHA256":
        return hashlib.sha256(payload).hexdigest().upper()
    return hashlib.md5(payload).hexdigest().upper()


def build_url(base_url, path):
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def shell_join(parts):
    return " ".join(shlex.quote(part) for part in parts)


def build_form_curl(args, params, signature):
    app_code = args.app_code if args.show_sensitive else mask(args.app_code)
    qf_signature = signature if args.show_sensitive else "<redacted-signature>"
    body_params = display_params(params, args.show_sensitive)
    headers = [
        "Content-Type: application/x-www-form-urlencoded",
        f"X-QF-APPCODE: {app_code}",
        f"X-QF-SIGN: {qf_signature}",
    ]
    if args.sign_type.upper() == "SHA256":
        headers.append("X-QF-SIGNTYPE: SHA256")

    command = ["curl", "-sS", "-X", args.method.upper(), build_url(args.base_url, args.path)]
    for header in headers:
        command.extend(["-H", header])
    command.extend(["--data-raw", encoded_params(body_params)])
    return shell_join(command)


def build_checkout_url(args, params, signature):
    signed = display_params(params, args.show_sensitive)
    signed["sign"] = signature if args.show_sensitive else "<redacted-signature>"
    ordered = [(key, signed[key]) for key in sorted(signed) if key != "sign"]
    ordered.append(("sign", signed["sign"]))
    return build_url(args.base_url, args.path) + "?" + urlencode(ordered)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["form", "checkout"], default="form")
    parser.add_argument(
        "--env",
        choices=sorted(ENVIRONMENTS),
        default=os.getenv("QFPAY_ENV", "live-testing"),
        help="QFPay environment alias. QA maps to Sandbox/openapi-int; gray maps to gray-openapi-hk.",
    )
    parser.add_argument("--base-url", default=os.getenv("QFPAY_BASE_URL"), help="Override the environment base URL")
    parser.add_argument("--path", required=True, help="API path, e.g. /trade/v1/query")
    parser.add_argument("--method", default="POST", help="HTTP method for form cURL output")
    parser.add_argument("--app-code", default=os.getenv("QFPAY_APP_CODE"), help="QFPay app code. Prefer env or --prompt-app-code.")
    parser.add_argument(
        "--client-key",
        default=os.getenv("QFPAY_CLIENT_KEY"),
        help="QFPay signing key. Prefer env or --prompt-client-key; command-line values may be visible.",
    )
    parser.add_argument("--prompt-app-code", action="store_true", help="Prompt for app code instead of putting it in shell history.")
    parser.add_argument("--prompt-client-key", action="store_true", help="Prompt for client key without terminal echo.")
    parser.add_argument("--show-sensitive", action="store_true", help="Print usable signature, cURL, or checkout URL. Default redacts them.")
    parser.add_argument("--sign-type", choices=["MD5", "SHA256"], default="MD5")
    parser.add_argument("--params-json", help="JSON object or @file.json with request parameters")
    parser.add_argument("--param", action="append", default=[], type=parse_key_value, help="Request parameter as KEY=VALUE")
    parser.add_argument("--keep-empty", action="store_true", help="Keep empty values in signing input")
    args = parser.parse_args()

    if args.prompt_app_code:
        args.app_code = input("QFPAY_APP_CODE: ").strip()
    if args.prompt_client_key:
        args.client_key = getpass.getpass("QFPAY_CLIENT_KEY: ")

    if not args.client_key:
        raise SystemExit("client key is required via --prompt-client-key, --client-key, or QFPAY_CLIENT_KEY")
    if args.mode == "form" and not args.app_code:
        raise SystemExit("app code is required for form mode via --prompt-app-code, --app-code, or QFPAY_APP_CODE")
    if any(arg == "--client-key" or arg.startswith("--client-key=") for arg in sys.argv[1:]):
        print("warning: --client-key may be captured in shell history or process lists; prefer --prompt-client-key", file=sys.stderr)

    base_url = args.base_url or ENVIRONMENTS[args.env]
    params = load_params(args)
    signature = make_signature(params, args.client_key, args.sign_type)
    output_params = display_params(params, args.show_sensitive)
    result = {
        "mode": args.mode,
        "environment": args.env,
        "base_url": base_url,
        "sign_type": args.sign_type.upper(),
        "sensitive_output": args.show_sensitive,
        "redaction_note": "" if args.show_sensitive else "signature, app identifiers, and sensitive params are redacted; use --show-sensitive only in a safe local terminal",
        "canonical_without_client_key": canonical_string(output_params),
        "signature": signature if args.show_sensitive else "<redacted-signature>",
        "encoded_params": encoded_params(output_params),
    }

    if args.mode == "checkout":
        args.base_url = base_url
        result["url"] = build_checkout_url(args, params, signature)
    else:
        args.base_url = base_url
        result["curl"] = build_form_curl(args, params, signature)

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
