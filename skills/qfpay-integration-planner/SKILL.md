---
name: qfpay-integration-planner
description: "Plan a QFPay payment integration for a web shop, mobile app, physical store, restaurant, POS/ECR, kiosk, or self-service machine. Use when selecting Hosted Checkout, Element SDK, MPM, CPM, POS API, payment channel, Sandbox path, or a merchant implementation plan."
---

# QFPay Integration Planner

先讀取 `../../references/contract-manifest.json`，再用 `qfpay docs` 或 `../../references/qfpay-openapi-reference.zh-Hant.md` 核對當前 contract。不可憑記憶猜 endpoint、`pay_type`、currency 或 channel eligibility。

1. 收集 storefront/device、customer present/not present、region、currency、payment methods、backend language、callback URL、是否需要 refund/pre-authorisation。
2. 選擇 integration：低客製化網店優先 Hosted Checkout；自訂 online checkout 用 Element SDK；商戶展示 QR 用 MPM；掃顧客付款碼用 CPM；POS/ECR 依官方裝置 contract。若 merchant configuration 未確認，標為未確認而非假設可用。
3. 預設 Sandbox（QA）。只產出 Sandbox 測試步驟；不得把 profile 升級至 Production。
4. 為每個 flow 列出 backend signing、Callback、Transaction Enquiry、Idempotency、timeout/`UNKNOWN` recovery、refund 與 reconciliation 的責任位置。
5. 回答最後必須包含：選定 integration、environment、查證的 contract/source、未確認項目及下一個安全測試。

需要共通 state/secret 規則時讀取 `../qfpay-payment-best-practices/SKILL.md`。需要詳細 online/in-store API 欄位時，再讀取 shared reference；不要把整份 reference 複製到回覆或程式碼。
