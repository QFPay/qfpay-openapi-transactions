# QFPay OpenAPI Transactions Skill

这是一个面向 Codex/Agent 的 QFPay OpenAPI 交易操作 skill。它整理了下单、查询、退款、撤销、冲正、关闭、预授权和回调验签等常用交易流程。

## 环境

| 环境 | Base URL |
| --- | --- |
| QA | `https://openapi-int.qfapi.com` |
| 线上测试 | `https://test-openapi-hk.qfapi.com` |
| 生产 | `https://openapi-hk.qfapi.com` |

## 目录

- `SKILL.md`：skill 入口和使用流程。
- `references/qfpay-openapi-reference.zh-CN.md`：中文交易操作参考。
- `references/qfpay-openapi-reference.md`：英文交易操作参考。
- `scripts/qfpay_sign.py`：生成签名和 cURL 示例，不会主动发送请求。
- `agents/openai.yaml`：Agent UI 元数据。

## 快速使用

优先让 Agent 阅读 `SKILL.md` 和中文参考文档，再根据目标环境、`app_code`、`client_key`、支付方式和金额执行操作。

生成查询接口签名和 cURL 示例：

```bash
QFPAY_APP_CODE=your_app_code \
QFPAY_CLIENT_KEY=your_client_key \
scripts/qfpay_sign.py \
  --env qa \
  --path /trade/v1/query \
  --param syssn=20260902281000020000000015
```

不要提交真实 `app_code`、`client_key`、`.env` 或接口响应里的敏感数据。
