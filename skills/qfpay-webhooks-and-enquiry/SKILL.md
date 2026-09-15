---
name: qfpay-webhooks-and-enquiry
description: "Build or review QFPay asynchronous Callback handling, signature verification, duplicate and out-of-order recovery, Transaction Enquiry, timeout handling, and fulfilment state machines. Use for webhook/callback, payment status, unknown payment, 1143, 1145, 1298, timeout, reconciliation, or fulfilment."
---

# QFPay Webhooks And Enquiry

1. 收取原始 callback bytes，從 `X-QF-SIGN` 驗證 `MD5(raw_body + client_key)`；驗證失敗不得處理或回 `SUCCESS`。
2. parse 後允許未知欄位。以 `syssn` + `out_trade_no` 建立 durable idempotency/event record，並處理 duplicate 和 out-of-order callbacks。
3. 將結果正規化為 `SUCCESS`、`FAILED`、`PROCESSING`、`UNKNOWN` 或 `ACTION_REQUIRED`。transport `200` 或單一 `0000` response 不是自動 fulfilment。
4. `1143`、`1145`、`1298`、timeout、network error 或本地 callback/state 衝突時：鎖定原 order，維持相同 identifier，執行 Transaction Enquiry；禁止重送 payment/refund 或履約。
5. 只在 verified Callback、Transaction Enquiry 和 merchant fulfilment rule 一致時履約。每項 transition 保存 trace ID、request hash、來源與決策，不保存 secret/PII。

用 `qfpay callback verify --body-file … --signature …` 驗證 fixture，`qfpay callback replay …` 測試 local idempotency，或 `qfpay callback listen --port 3001` 啟動僅 loopback、Sandbox-only 的 local listener；它們都不會儲存 raw payload。bundled MCP 只提供 read-only enquiry preview/QA host-controlled query，不能用它執行 funds action。
