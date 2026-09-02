#!/usr/bin/env python3
"""Generate QFPay signatures and cURL snippets without sending requests."""

import argparse
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
    "production": "https://openapi-hk.qfapi.com",
    "prod": "https://openapi-hk.qfapi.com",
}


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
    headers = [
        "Content-Type: application/x-www-form-urlencoded",
        f"X-QF-APPCODE: {args.app_code}",
        f"X-QF-SIGN: {signature}",
    ]
    if args.sign_type.upper() == "SHA256":
        headers.append("X-QF-SIGNTYPE: SHA256")

    command = ["curl", "-sS", "-X", args.method.upper(), build_url(args.base_url, args.path)]
    for header in headers:
        command.extend(["-H", header])
    command.extend(["--data-raw", encoded_params(params)])
    return shell_join(command)


def build_checkout_url(args, params, signature):
    signed = dict(params)
    signed["sign"] = signature
    ordered = [(key, signed[key]) for key in sorted(signed) if key != "sign"]
    ordered.append(("sign", signature))
    return build_url(args.base_url, args.path) + "?" + urlencode(ordered)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["form", "checkout"], default="form")
    parser.add_argument(
        "--env",
        choices=sorted(ENVIRONMENTS),
        default=os.getenv("QFPAY_ENV", "live-testing"),
        help="QFPay environment alias. QA maps to Sandbox/openapi-int.",
    )
    parser.add_argument("--base-url", default=os.getenv("QFPAY_BASE_URL"), help="Override the environment base URL")
    parser.add_argument("--path", required=True, help="API path, e.g. /trade/v1/query")
    parser.add_argument("--method", default="POST", help="HTTP method for form cURL output")
    parser.add_argument("--app-code", default=os.getenv("QFPAY_APP_CODE"))
    parser.add_argument("--client-key", default=os.getenv("QFPAY_CLIENT_KEY"))
    parser.add_argument("--sign-type", choices=["MD5", "SHA256"], default="MD5")
    parser.add_argument("--params-json", help="JSON object or @file.json with request parameters")
    parser.add_argument("--param", action="append", default=[], type=parse_key_value, help="Request parameter as KEY=VALUE")
    parser.add_argument("--keep-empty", action="store_true", help="Keep empty values in signing input")
    args = parser.parse_args()

    if not args.client_key:
        raise SystemExit("client key is required via --client-key or QFPAY_CLIENT_KEY")
    if args.mode == "form" and not args.app_code:
        raise SystemExit("app code is required for form mode via --app-code or QFPAY_APP_CODE")

    base_url = args.base_url or ENVIRONMENTS[args.env]
    params = load_params(args)
    signature = make_signature(params, args.client_key, args.sign_type)
    result = {
        "mode": args.mode,
        "environment": args.env,
        "base_url": base_url,
        "sign_type": args.sign_type.upper(),
        "canonical_without_client_key": canonical_string(params),
        "signature": signature,
        "encoded_params": encoded_params(params),
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
