---
name: qfpay-auth-and-signing
description: "Implement QFPay server-side credentials, environment selection, MD5/SHA256 request signatures, Hosted Checkout signing, and callback verification without leaking secrets. Use for app_code, client_key, X-QF-SIGN, X-QF-APPCODE, signing bugs, or QFPay authentication setup."
---

# QFPay Auth And Signing

先讀取 `../../references/qfpay-openapi-reference.zh-Hant.md` 的「簽名與請求」；具體 algorithm 必須再以 canonical contract 核對。

1. 只由 backend service 讀取已綁定 environment、merchant 和 store 的 secret。Agent、frontend、MCP tool schema 和一般 command line 一律不接收 `client_key`。
2. 預設 Sandbox/QA；禁止混用 environment 的 base URL 和 credential。只有 policy-controlled service 可使用非 QA profile。
3. 標準 API：去掉 `null`/空字串，ASCII sort，使用實際傳送的字串（包括 compact `extend_info` JSON），最後直接附加 `client_key` 後做 contract 指定的 MD5/SHA256。
4. Hosted Checkout：由 backend 產生 signed URL；不可把完整 URL、`appcode` 或 `sign` 回傳到 Agent context。前端只取得其本次 redirect 所需的 server response。
5. Callback：對原始 bytes 做 `MD5(raw_body + client_key)`，使用 timing-safe compare。不得先 parse/re-serialize JSON。

本 repo 的 `qfpay` CLI 只允許 prompt/environment 讀取 secret，預設輸出脫敏；`--show-sensitive` 需要外部 operator capability。發現 secret 進入 repository/log/context 時，停止資金動作並輪換 key。
