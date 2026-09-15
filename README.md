# QFPay Payment Skills

這個 repository 是 QFPay Developer Agent Enablement MVP：一組可獨立觸發的 Skills、可安裝的 `qfpay` developer CLI、Sandbox templates，以及 local read-only stdio MCP。它不是 Remote MCP，亦不包含 merchant credential 或 Production payment execution。

## 安全邊界

- 預設 environment 是 Sandbox/QA。Agent 不得自行將 profile 切至 Production。
- `client_key` 只能由 backend secret manager/Vault/KMS 使用；不可放進 frontend、repo、log、Agent context、MCP argument 或普通 CLI flag。
- local MCP 只提供 docs、pay_type 和 Transaction Enquiry preview/由 host 明確授權的 QA query；沒有 payment、checkout signed URL、refund、reversal、close 或 pre-authorisation tools。
- Remote MCP、OAuth 2.1、merchant/store scope、Approval Center、Vault/KMS broker、rate limit、audit trail 與 Streamable HTTP 尚未交付。因此不可宣稱 external/Production ready。

## 安裝與開始

這個 package 已具備 npm CLI manifest（`@qfpay/cli`），但尚未配置公開 registry/release signing；在 repository 內測試可用：

```bash
npm install
npm exec -- qfpay --version
npm exec -- qfpay agent setup
npm exec -- qfpay docs search "refund timeout"
npm exec -- qfpay docs /integration/common-api/transaction-enquiry
npm exec -- qfpay transaction get --out-trade-no ORDER_1001
npm exec -- qfpay test signature
```

CLI 需要 Python 3.10+。如 Python 不是 `python3`/`python`，設定 `QFPAY_PYTHON` 指向其可執行檔。`qfpay agent setup --agent auto|codex|claude-code|cursor` 只輸出各 host 可採用的 secret-free local MCP fragment，不會寫入 host config 或 credential；請依各 host 目前官方說明選擇設定檔位置。`qfpay agent doctor` 驗證 Skill、Plugin、contract、CLI release 結構，並僅偵測（不讀取）已存在的 host 目錄。

## Skills

| Skill | 用途 |
| --- | --- |
| `qfpay-integration-planner` | 選擇 online、in-store、POS/ECR 或 kiosk integration。 |
| `qfpay-payment-best-practices` | 共通 security、state、Idempotency、funds-action 規則。 |
| `qfpay-auth-and-signing` | server-side credential、MD5/SHA256、Callback/Checkout signing。 |
| `qfpay-webhooks-and-enquiry` | Callback、Transaction Enquiry、UNKNOWN 與 fulfilment。 |
| `qfpay-docs` | contract、endpoint、pay_type 及 freshness 查證。 |
| `qfpay-go-live-review` | UAT、monitoring、reconciliation 與 Production readiness。 |

`SKILL.md` 是相容 router；新安裝優先使用 `skills/` 內的細分 Skill。版本與 discovery metadata 在 [`.well-known/skills/index.json`](.well-known/skills/index.json)。

## CLI 與測試

```bash
qfpay init hosted-checkout --language node --output ./qfpay-checkout
qfpay init mpm --language node --output ./qfpay-mpm
qfpay lint ./qfpay-checkout
qfpay callback verify --body-file callback.json --signature "$X_QF_SIGN" --prompt-client-key
qfpay callback replay --body-file callback.json --signature "$X_QF_SIGN" --prompt-client-key
qfpay callback listen --port 3001 --prompt-client-key
qfpay mcp serve
```

templates 只產生 Sandbox-first server-side 程式碼與 `.env.example`，不會輸出實際 secret。`qfpay callback replay/listen` 只保存 hashed idempotency material 和 event fingerprint，不回顯或持久化 raw payload；listener 永遠只綁定 `127.0.0.1` 並且只支援 Sandbox。`qfpay_sign.py` 預設遮罩 signature 和敏感值；輸出可用的敏感材料需由本機 operator 設定 `QFPAY_ALLOW_SENSITIVE_OUTPUT=1`。

執行 release checks：

```bash
python3 scripts/check_contract_freshness.py
python3 scripts/check_paytype_coverage.py
python3 scripts/check_evals.py
python3 scripts/build_release_manifest.py --check
python3 scripts/check_public_release.py --preview
python3 scripts/qfpay_mcp_server.py --self-test
python3 -m unittest discover -s tests -v
```

## Release gate

Production 或 Remote MCP 發布前必須完成：fresh canonical OpenAPI contract、channel eligibility、OAuth 2.1、merchant/store scope、Vault/KMS credential broker、獨立 human approval（request hash/amount/currency/expiry binding）、durable idempotency/audit、payment state machine、redaction/DLP、rate limit、Host/Origin validation、MCP conformance、fault-injection 和 UAT evidence。任一項缺失即 **NO-GO**。

公開 package 的可重現性、checksum 和人工作業請看 [`docs/PUBLISHING.md`](docs/PUBLISHING.md)。`check_public_release.py` 對這個 internal preview 會故意失敗，直到組織補上已核准 licence、官方網址、OpenAPI SHA-256 和乾淨的 reviewed Git tag；這不會放寬 Production/Remote MCP 的 NO-GO 邊界。

目前 manifest 記錄的 canonical URL 在 2026-09-15 回傳的是 `OpenAPI Plant Store` 示例，不是 QFPay OpenAPI；因此 source status 為 `blocked`，不得填入其 hash 或公開發布。取得 QFPay 官方 canonical URL 後，先用 `scripts/verify_contract_source.py` 驗證文件身份，再更新 manifest。
