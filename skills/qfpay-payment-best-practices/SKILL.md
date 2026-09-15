---
name: qfpay-payment-best-practices
description: "Apply non-negotiable QFPay payment safety, state, idempotency, callback, refund, and Production rules. Use for any QFPay payment design, code, test, incident, retry, refund, reversal, pre-authorisation, or fulfilment decision."
---

# QFPay Payment Best Practices

以下規則不可例外：

- 不得把 `client_key` 放入 frontend、mobile app、repository、log、Agent context、MCP argument 或一般 CLI flag。只在 server-side secret manager/Vault/KMS 使用。
- 不得生成未被 `../../references/contract-manifest.json` 對應 contract 支援的 endpoint、`pay_type`、currency 或 capability。
- HTTP timeout、network error、`1143`、`1145`、`1298` 不是失敗。它們進入 `PROCESSING` 或 `UNKNOWN`；禁止重送 payment/refund/fulfilment，先 Transaction Enquiry。
- `respcd=0000` 不單獨等於可以履約。以 verified Callback 加 Transaction Enquiry 和 merchant fulfilment rule 判定最終狀態。
- 每筆 Payment 和 Refund 要有唯一的 `out_trade_no`。相同意圖重試必須沿用原值，不可以換號規避 pending/duplicate。
- Callback 驗簽、idempotent、可接受 duplicate/out-of-order/未知欄位。未驗簽或未成功處理不得回傳 `SUCCESS`。
- Refund 前驗證原交易、可退餘額、currency 和 channel rule；成功 QR payment 用 Refund，不用 Reversal。
- Refund、Reversal、Close、pre-authorisation capture/Unfreeze 採 `prepare → human approve → execute → enquire`。approval 必須來自獨立 Approval Center，並綁定 merchant、store、operation、amount、currency、request hash、expiry；Agent 不可自行提供 confirmation boolean。
- 不得由 Agent 把 Sandbox 改成 Production。Production 需 merchant 授權與 Go-live review。

使用一致狀態：`SUCCESS`、`FAILED`、`PROCESSING`、`UNKNOWN`、`ACTION_REQUIRED`。術語見 `../../references/terminology.md`。
