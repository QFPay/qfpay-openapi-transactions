---
name: qfpay-openapi-transactions
description: "Route broad QFPay OpenAPI integration requests to the versioned QFPay payment skills. Use when a task spans QFPay payment planning, Sandbox integration, credentials/signing, callback/Transaction Enquiry, API documentation, refund safety, or Go-live review."
---

# QFPay Payment Skills Router

這是相容的 umbrella Skill，不再把所有 QFPay 規則塞進一份文件。優先選取最窄的 child Skill：

| 需要 | Skill |
| --- | --- |
| 選擇 web/app/POS/kiosk integration | `skills/qfpay-integration-planner/SKILL.md` |
| 共通 payment safety、state、retry、funds rule | `skills/qfpay-payment-best-practices/SKILL.md` |
| Credentials、MD5/SHA256、Hosted Checkout signing | `skills/qfpay-auth-and-signing/SKILL.md` |
| Callback、Transaction Enquiry、UNKNOWN、fulfilment | `skills/qfpay-webhooks-and-enquiry/SKILL.md` |
| 最新文件、API path、pay_type、contract | `skills/qfpay-docs/SKILL.md` |
| Sandbox-to-Production review | `skills/qfpay-go-live-review/SKILL.md` |

每個 QFPay 回答都要說明：選定 integration、environment、引用的 contract/source、未確認事項及下一個安全步驟。預設使用 Sandbox/QA；不得由 Agent 自行切到 Production 或執行任何資金動作。

執行 deterministic checks：

```bash
qfpay docs search "Transaction Enquiry"
qfpay test signature
python3 scripts/check_contract_freshness.py
python3 scripts/check_paytype_coverage.py
```

`qfpay mcp serve` 只提供 local stdio、read-only documentation/pay_type/Transaction Enquiry 能力：不接受 credential、merchant/store/environment 或 funds-action arguments。它不是 Remote MCP；OAuth、scope、Vault/KMS、Approval Center、idempotency/audit service、rate limit、Host/Origin validation 未完成前，Remote MCP 和 `execute=true` 資金動作均為 **NO-GO**。
