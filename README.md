# QFPay OpenAPI Transactions Skill

这是一个面向 Codex/Agent 的 QFPay OpenAPI 交易操作 skill。它整理了下单、查询、退款、撤销、冲正、关闭、预授权和回调验签等常用交易流程。

## 环境

| 环境 | Base URL |
| --- | --- |
| QA | `https://openapi-int.qfapi.com` |
| 线上测试 | `https://test-openapi-hk.qfapi.com` |
| 灰度 | `https://gray-openapi-hk.qfapi.com` |
| 生产 | `https://openapi-hk.qfapi.com` |

## 目录

- `SKILL.md`：skill 入口和使用流程。
- `references/qfpay-openapi-reference.zh-CN.md`：中文交易操作参考。
- `references/qfpay-openapi-reference.md`：英文交易操作参考。
- `scripts/qfpay_sign.py`：生成签名和 cURL 示例，不会主动发送请求，默认脱敏签名、app code 和常见敏感参数。
- `scripts/qfpay_mcp_server.py`：本地 stdio MCP server，提供下单、查询、退款、冲正、close、预授权和 pay_type 查询工具。
- `scripts/check_paytype_coverage.py`：检查中英文参考是否覆盖官方和专项页面里的 pay_type。
- `agents/openai.yaml`：Agent UI 元数据。

## 快速使用

优先让 Agent 阅读 `SKILL.md` 和中文参考文档，再根据目标环境、`app_code`、`client_key`、支付方式和金额执行操作。真实凭证只用于当前操作，回复和日志必须脱敏。

生成查询接口签名和 cURL 示例：

```bash
python3 scripts/qfpay_sign.py \
  --env qa \
  --path /trade/v1/query \
  --prompt-app-code \
  --prompt-client-key \
  --param syssn=20260902281000020000000015
```

默认输出会脱敏 `X-QF-SIGN`、`app_code`、付款码和常见客户敏感参数。只有在本地安全终端需要可执行 cURL/URL 时才加 `--show-sensitive`。

不要提交真实 `app_code`、`client_key`、`.env`、签名或接口响应里的敏感数据。

## MCP Server

本仓库也可以作为本地 stdio MCP server 使用。建议把凭证放在 MCP 客户端的本地环境变量配置里，不要写进仓库。

示例配置：

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

工具默认 `execute=false`，只返回脱敏签名预览；需要真正请求 QFPay 时传 `execute=true`。灰度和生产环境还必须传 `confirm_production=true`；退款、冲正、close、预授权扣款和解冻还必须传 `confirm_funds_action=true`。

如果本机 Python 报 `CERTIFICATE_VERIFY_FAILED`，先安装/修复 Python CA 证书，或在 MCP 客户端环境里指定 CA bundle：

```json
{
  "env": {
    "QFPAY_CA_BUNDLE": "/path/to/cacert.pem"
  }
}
```

server 会优先使用 `QFPAY_CA_BUNDLE`；未设置时，如果当前 Python 安装了 `certifi`，会自动使用 `certifi` 的 CA bundle。

## 覆盖检查

更新 QFPay 文档后运行：

```bash
python3 scripts/check_paytype_coverage.py
```
