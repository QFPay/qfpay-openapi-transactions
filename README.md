# QFPay OpenAPI Transactions Skill

English | [简体中文](README.zh-CN.md)

A QFPay OpenAPI transaction skill for Codex and other agents. It covers common transaction workflows, including payment creation, queries, refunds, cancellation, reversal, closing, preauthorization, and callback signature verification.

## Environments

| Environment | Base URL |
| --- | --- |
| QA | `https://openapi-int.qfapi.com` |
| Online testing | `https://test-openapi-hk.qfapi.com` |
| Gray release | `https://gray-openapi-hk.qfapi.com` |
| Production | `https://openapi-hk.qfapi.com` |

## Repository Structure

- `SKILL.md`: Skill entry point and workflow.
- `references/qfpay-openapi-reference.zh-CN.md`: Transaction reference in Chinese.
- `references/qfpay-openapi-reference.md`: Transaction reference in English.
- `scripts/qfpay_sign.py`: Generates signatures and cURL examples without sending requests. Signatures, app codes, and common sensitive parameters are redacted by default.
- `scripts/qfpay_mcp_server.py`: Local stdio MCP server with tools for payment creation, queries, refunds, reversal, closing, preauthorization, and pay_type lookup.
- `scripts/check_paytype_coverage.py`: Checks whether both reference documents cover the pay_type values from the official and dedicated documentation pages.
- `agents/openai.yaml`: Agent UI metadata.

## Quick Start

Have the agent read `SKILL.md` and the reference document in your preferred language first, then perform the operation using the target environment, `app_code`, `client_key`, payment method, and amount. Use real credentials only for the current operation, and redact them in responses and logs.

Generate a signature and cURL example for the query endpoint:

```bash
python3 scripts/qfpay_sign.py \
  --env qa \
  --path /trade/v1/query \
  --prompt-app-code \
  --prompt-client-key \
  --param syssn=20260902281000020000000015
```

The default output redacts `X-QF-SIGN`, `app_code`, payment codes, and common sensitive customer parameters. Add `--show-sensitive` only when you need an executable cURL command or URL in a secure local terminal.

Do not commit real `app_code` or `client_key` values, `.env` files, signatures, or sensitive data from API responses.

## MCP Server

This repository can also run as a local stdio MCP server. Store credentials in the MCP client's local environment variable configuration and keep them out of the repository.

Example configuration:

```json
{
  "mcpServers": {
    "qfpay-openapi-transactions": {
      "command": "python3",
      "args": ["/Users/sato/Documents/Codex/2026-09-02/ni/qfpay-openapi-transactions/scripts/qfpay_mcp_server.py"],
      "env": {
        "QFPAY_ENV": "qa",
        "QFPAY_APP_CODE": "replace-with-app-code",
        "QFPAY_CLIENT_KEY": "replace-with-client-key"
      }
    }
  }
}
```

Tools default to `execute=false` and return only a redacted signature preview. Set `execute=true` to send a request to QFPay. Gray release and production environments also require `confirm_production=true`; refunds, reversal, closing, preauthorization capture, and release also require `confirm_funds_action=true`.

If your local Python reports `CERTIFICATE_VERIFY_FAILED`, install or repair its CA certificates, or specify a CA bundle in the MCP client's environment:

```json
{
  "env": {
    "QFPAY_CA_BUNDLE": "/path/to/cacert.pem"
  }
}
```

The server uses `QFPAY_CA_BUNDLE` first. If it is unset and `certifi` is installed in the current Python environment, the server automatically uses its CA bundle.

## Coverage Check

After updating the QFPay documentation, run:

```bash
python3 scripts/check_paytype_coverage.py
```
