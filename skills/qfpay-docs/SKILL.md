---
name: qfpay-docs
description: "Search and verify versioned QFPay API documentation, OpenAPI contract metadata, pay_type, endpoint, currency, channel eligibility, and deprecated capability. Use before generating QFPay request fields, API paths, integration code, migrations, or production guidance."
---

# QFPay Docs

使用 deterministic CLI，而非記憶：

```bash
qfpay docs /integration/common-api/transaction-enquiry
qfpay docs search "refund timeout"
qfpay docs api POST /trade/v1/payment
python3 scripts/check_contract_freshness.py
python3 scripts/check_paytype_coverage.py
```

先讀取 `../../references/contract-manifest.json`，並在回答中標示 contract version/source。若欄位、pay_type、currency、merchant configuration 或 deprecated 狀態沒有官方證據，清楚標為「未確認」，不要猜測。

公開/Production guidance 必須先驗證 contract snapshot 未過期；最新文件可從 `https://sdk.qfapi.com/llms.txt` 和其 Traditional Chinese index 取得。此 Skill 只負責文件和 contract；即時商戶資料由受 scope 保護的 MCP/Gateway 處理。
