# QFPay OpenAPI 精要參考（繁體中文）

> Contract snapshot：`2026-09-15`。正式欄位、channel eligibility、currency 及 deprecated 狀態必須以 [QFPay OpenAPI](https://sdk.qfapi.com/openapi.json) 為準；在 Production 發布前，以 `qfpay docs` 及 `scripts/check_contract_freshness.py` 重新確認。

## 環境與憑據

| 環境 | Base URL | 用途 |
| --- | --- | --- |
| Sandbox（QA） | `https://openapi-int.qfapi.com` | 開發及整合測試；預設環境。 |
| Live Testing | `https://test-openapi-hk.qfapi.com` | 測試帳戶流程；確認資金性質。 |
| Gray | `https://gray-openapi-hk.qfapi.com` | 僅限 QFPay 指定的預發布驗證。 |
| Production | `https://openapi-hk.qfapi.com` | 真實支付及結算。 |

- `client_key` 只可保留在 merchant 的 server-side secret manager、Vault 或 KMS；不得放入 frontend、mobile app、repository、log、Agent context 或 MCP arguments。
- `app_code`、`mchid`、payment code、card／身份資料、`X-QF-SIGN` 及 Hosted Checkout `sign` 均視為敏感資料。
- 不得由 Agent 把 Sandbox profile 改成 Production。Production 必須經 merchant 的 Go-live decision 與平台 policy 批准。

## 簽名與請求

標準 form API：刪除 `null`／空字串，按 ASCII key 排序，以 `&` 連接成 `key=value`，最後直接附加 `client_key`，採用 contract 指定的 MD5 或 SHA256，輸出大寫摘要。不要把 signature 本身加入簽名。

Hosted Checkout 只可由 backend 簽發；`appcode` 與 `sign` 不可經由 Agent/MCP 回傳。Callback signature 則是 `MD5(raw JSON body + client_key)`，不是排序後欄位。

## Payment state 與 Idempotency

| 狀態 | 規則 |
| --- | --- |
| `SUCCESS` | 僅在已驗證 callback 與 Transaction Enquiry 符合 merchant 履約規則後，才可履約。 |
| `FAILED` | 對賬原交易後再決定下一步。 |
| `PROCESSING` | 維持同一個 `out_trade_no`，延遲後再 Transaction Enquiry。 |
| `UNKNOWN` | 禁止重送付款、退款或履約；先以同一識別字查詢。 |
| `ACTION_REQUIRED` | transport/API response 未能證明最終業務狀態；以 callback + Transaction Enquiry 完成判定。 |

`1143`、`1145`、`1298`、timeout 及 network error 都不能被描述為 payment failed。每個 Payment 和 Refund 均使用唯一、可追蹤的 `out_trade_no`；相同業務意圖要重試時，沿用原來的值。

## Callback、退款與 Production

- Callback 要先驗簽，按 `syssn` + `out_trade_no` idempotent 處理，接受 duplicate、out-of-order 及未知欄位；僅在成功處理後回傳 HTTP `200` 與 `SUCCESS`。
- Refund 前驗證原交易成功、可退餘額、currency、channel rule 及唯一 refund order。成功 QR payment 用 Refund，不可用 Reversal。
- Refund、Reversal、Close、pre-authorisation capture 和 Unfreeze 都是資金動作，必須 `prepare → human approve → execute → enquire`；Approval 必須由獨立的 Approval Center 發出並綁定 merchant、store、operation、amount、currency、request hash 和 expiry。

完整繁中頁面請透過 `https://sdk.qfapi.com/_llms/zh-hant.md` 取得；此檔僅保存 core rules，避免複製完整 API reference。
