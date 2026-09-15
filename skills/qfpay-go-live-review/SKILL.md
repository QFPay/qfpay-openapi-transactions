---
name: qfpay-go-live-review
description: "Perform a QFPay security, UAT, monitoring, reconciliation, and production-readiness review without switching environments or executing payments. Use for go-live, Production readiness, launch checklist, compliance review, UAT, monitoring, or QFPay migration approval."
---

# QFPay Go-live Review

產出 checklist，不自行切換 Production 或執行 payment。逐項確認：

1. canonical contract、pay_type × region × channel × currency × merchant eligibility 已重新核對，沒有 deprecated field。
2. client_key 僅在 server-side secret manager；secret scan、log redaction、DLP 和 rotation process 已驗證。
3. Callback raw-body verification、unknown field tolerance、durable Idempotency、out-of-order/duplicate test 均通過。
4. `SUCCESS`/`FAILED`/`PROCESSING`/`UNKNOWN`/`ACTION_REQUIRED` state machine 已實作；timeout/`1143`/`1145`/`1298` 都先 Transaction Enquiry，且 UNKNOWN 不履約、不重送。
5. Refund、Reversal、Close、capture、Unfreeze 有 prepare/approve/execute/enquire、human/dual approval、request hash、expiry、audit trail 和 reconciliation。
6. monitoring 包含 trace ID、rate limit、callback failure、UNKNOWN ageing、reconciliation、alert/escalation；資料不含 secret/PII。
7. Sandbox UAT、rollback、merchant/Store scope、Production approver 與 ownership 已記錄。

如缺少 OAuth 2.1、merchant/store scope、Vault/KMS broker、independent Approval Center、audit evidence、rate limit 或 Remote MCP Host/Origin validation，結果必須是 **NO-GO**，並列為 platform release gate。
