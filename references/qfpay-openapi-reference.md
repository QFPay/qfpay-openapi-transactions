# QFPay OpenAPI Reference

Snapshot date: 2026-09-09. Verify current behavior against the QFPay documentation before production go-live.

Source URLs:

- https://sdk.qfapi.com/llms.txt
- https://sdk.qfapi.com/integration/preparation/credentials-and-merchant-structure
- https://sdk.qfapi.com/integration/preparation/authentication-and-signature
- https://sdk.qfapi.com/integration/preparation/environments
- https://sdk.qfapi.com/integration/api-reference/request-format
- https://sdk.qfapi.com/integration/api-reference/response-format
- https://sdk.qfapi.com/integration/api-reference/paytypes
- https://sdk.qfapi.com/integration/api-reference/status-codes
- https://sdk.qfapi.com/integration/in-store/MPM
- https://sdk.qfapi.com/integration/in-store/CPM
- https://sdk.qfapi.com/integration/online-shop/integration-by-use-case/web-payment
- https://sdk.qfapi.com/integration/online-shop/integration-by-use-case/wap-payment
- https://sdk.qfapi.com/integration/online-shop/integration-by-use-case/in-app-payment
- https://sdk.qfapi.com/integration/online-shop/integration-by-payment-type/alipay/alipay-wap-h5-payments
- https://sdk.qfapi.com/integration/online-shop/checkout-integration/checkout
- https://sdk.qfapi.com/integration/online-shop/checkout-integration/payment-element
- https://sdk.qfapi.com/integration/common-api/transaction-enquiry
- https://sdk.qfapi.com/integration/common-api/refund
- https://sdk.qfapi.com/integration/common-api/reversal
- https://sdk.qfapi.com/integration/common-api/async-notifications
- https://sdk.qfapi.com/integration/online-shop/integration-by-use-case/preauth
- https://sdk.qfapi.com/integration/in-store/pos-api/app-call-app

## Table Of Contents

- Environments and credentials
- Signing
- Common payment parameters
- Complete pay_type list
- Payment scenario matrix
- Payment flow details
- Hosted Checkout
- Element SDK
- Query
- Refund
- Reversal and close
- Preauthorisation
- Async notifications
- Status codes and retry policy
- Android App-to-App POS SDK

## Environments And Credentials

Base URLs:

| Business name | Official docs name | Base URL | Use |
| --- | --- | --- | --- |
| QA | Sandbox | `https://openapi-int.qfapi.com` | Simulated development/testing. Does not deduct real funds. |
| 线上测试 | Live Testing | `https://test-openapi-hk.qfapi.com` | Real wallet flow with test accounts. No settlement; refund immediately if real payment methods are used. |
| 灰度 | Gray | `https://gray-openapi-hk.qfapi.com` | QFPay-designated gray/pre-release validation endpoint. Confirm credentials and funds behavior before use. |
| 生产 | Production | `https://openapi-hk.qfapi.com` | Live payments and settlement. |

The official English page uses `Sandbox`; many integrations refer to that same environment as `QA`. Treat QA/Sandbox as the `openapi-int` environment unless QFPay gives a merchant-specific QA URL.

The official Environments page currently lists three public environments: Production, Live Testing, and Sandbox. The gray endpoint above comes from QFPay-designated integration information; confirm merchant credentials are enabled before use.

Use only the four base URLs above for this integration unless QFPay explicitly issues a merchant-specific endpoint. Ignore older or generic examples such as `https://api.qfapi.com`.

Credentials:

| Name | Use |
| --- | --- |
| `app_code` | Store identifier. Send as `X-QF-APPCODE` for standard API calls. |
| `client_key` | Secret used for signatures. Keep server-side only. |
| `mchid` | Optional merchant/store identifier. Include only if QFPay issued it or the channel requires it. If not issued, omit it from both payload and signature. |

Use matching credentials and base URL from the same environment. Mixing QA, live-testing, gray, and production credentials or endpoints commonly causes authentication or signature errors.

Credential safety rules:

- Treat `app_code` as a sensitive merchant identifier and `client_key` as a secret.
- Do not put real `client_key` values in frontend code, mobile apps, repos, issues, PRs, logs, screenshots, or final replies.
- Do not pass `client_key` as a plaintext command-line argument. Prefer no-echo prompts, environment variables, or a secret manager.
- Treat `X-QF-SIGN` and Hosted Checkout `sign` as sensitive because they authorize the same parameter set.
- If credentials leak, stop money-moving actions, rotate `client_key`, then resume calls.

## Signing

Standard request signature:

1. Remove null and empty-string parameters.
2. Sort remaining request parameters by ASCII parameter name.
3. Join as `key=value` separated by `&`.
4. Append `client_key` directly with no delimiter.
5. Hash using MD5 by default, or SHA256 when requested by the API/config.
6. Uppercase the hex digest.
7. Send `X-QF-SIGN: <digest>`. Add `X-QF-SIGNTYPE: SHA256` only for SHA256.

Python implementation:

```python
import hashlib

def qfpay_sign(params, client_key, sign_type="MD5"):
    clean = {k: str(v) for k, v in params.items() if v is not None and str(v) != ""}
    canonical = "&".join(f"{k}={clean[k]}" for k in sorted(clean))
    data = (canonical + client_key).encode("utf-8")
    if sign_type.upper() == "SHA256":
        return hashlib.sha256(data).hexdigest().upper()
    return hashlib.md5(data).hexdigest().upper()
```

Important details:

- Sign the same parameters being sent. Do not sign `X-QF-SIGN`, `sign`, null fields, or empty strings.
- Keep parameter names and values case-sensitive.
- Use UTF-8.
- For object fields such as `extend_info`, send a compact JSON string and sign that exact string value.
- For Hosted Checkout, `sign` is a query parameter and must not be included in the signed source string.
- For callback verification, use raw JSON body + `client_key` and MD5, not sorted fields.

## Common Payment Parameters

Most `POST /trade/v1/payment` calls share these parameters:

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `txamt` | Yes | Int | Amount in smallest currency unit, e.g. `100` = 1.00. QFPay recommends > 200 to reduce risk-control failures. |
| `txcurrcd` | Yes | String(3) | ISO 4217 currency, e.g. `HKD`. Some methods support only HKD. |
| `pay_type` | Yes | String(6) | Payment method code. Confirm it is enabled for the merchant. |
| `out_trade_no` | Yes | String(128) | Unique merchant order ID. Must be unique per merchant across payments and refunds. |
| `txdtm` | Yes | String(20) | `YYYY-MM-DD HH:mm:ss`. |
| `auth_code` | CPM only | String(128) | Customer wallet barcode/QR authorisation code, one-time use. |
| `expired_time` | MPM/link only | String(3) | QR/link expiry in minutes. Default 30, min 5, max 120 where supported. |
| `goods_name` | Usually optional, app flows often required | String(64) | Keep short; QFPay says max 20 alphanumeric chars for some channels. UTF-8 for Chinese. |
| `mchid` | Conditional | String(16) | Include only if assigned or required. |
| `udid` | No | String(40) | Device identifier for internal tracking/reporting. |
| `notify_url` | No/recommended | String | Backend callback URL. |
| `return_url` | Browser/app flows | String | User redirect/deep link after payment. |
| `extend_info` | Conditional | JSON string | Channel-specific fields such as WeChat H5 scene info or real-name verification. |
| `limit_pay` | Optional | String | `no_credit` disables credit cards where supported. |
| `pay_tag` | Alipay optional | String(16) | Default `ALIPAYHK`; use `ALIPAYCN` for Mainland Alipay when applicable. |

Supported currencies listed by QFPay: `AED`, `CNY`, `EUR`, `HKD`, `IDR`, `JPY`, `MMK`, `MYR`, `SGD`, `THB`, `USD`, `CAD`, `AUD`.

## Complete pay_type List

The 34 pay types below match the official Payment Types page, checked on 2026-09-03. Actual availability still depends on the merchant's QFPay onboarding configuration.

| Channel | pay_type | Scenario | Recommended entry/result |
| --- | --- | --- | --- |
| Aggregated CPM | `800008` | WeChat, Alipay, UNIONPAY Quick Pass, PayMe customer-presented code | `/trade/v1/payment` with `auth_code` |
| Alipay | `800101` | MPM overseas merchants | `/trade/v1/payment`, returns `qrcode` |
| Alipay | `800108` | CPM overseas and HK merchants | `/trade/v1/payment` with `auth_code` |
| Alipay | `801101` | Online WEB overseas merchants | `/trade/v1/payment`, returns `pay_url` |
| Alipay | `801107` | Online WAP/H5 overseas merchants | `/trade/v1/payment`, returns `pay_url` |
| Alipay | `801110` | In-App overseas merchants | `/trade/v1/payment`, returns `pay_params` |
| AlipayHK | `801501` | MPM HK merchants | `/trade/v1/payment`, returns `qrcode` |
| AlipayHK | `801510` | In-App HK merchants | `/trade/v1/payment`, returns `pay_params` |
| AlipayHK | `801512` | Online WAP HK merchants | `/trade/v1/payment`, returns `pay_url` |
| AlipayHK | `801514` | Online WEB HK merchants | `/trade/v1/payment`, returns `pay_url` |
| WeChat Pay | `800201` | MPM / Web QR overseas and HK merchants | `/trade/v1/payment`, returns `qrcode` |
| WeChat Pay | `800208` | CPM overseas and HK merchants | `/trade/v1/payment` with `auth_code` |
| WeChat Pay | `800207` | JSAPI / Official Account payment | `/trade/v1/payment` with `sub_openid` |
| WeChat Pay | `800212` | H5 third-party mobile browser | `/trade/v1/payment` with `extend_info` |
| WeChat Pay | `800210` | In-App overseas and HK merchants | `/trade/v1/payment`, returns `pay_params` |
| WeChat Pay | `800213` | Mini Program payment | `/trade/v1/payment` with `sub_openid` |
| PayMe | `805801` | MPM HK merchants | `/trade/v1/payment`, returns `qrcode` |
| PayMe | `805808` | CPM HK merchants | `/trade/v1/payment` with `auth_code` |
| PayMe | `805814` | Online WEB HK merchants | `/trade/v1/payment`, returns `pay_url` |
| PayMe | `805812` | Online WAP HK merchants | `/trade/v1/payment`, returns `pay_url` |
| UNIONPAY Quick Pass | `800701` | MPM | `/trade/v1/payment`, returns `qrcode` |
| UNIONPAY Quick Pass | `800708` | CPM | `/trade/v1/payment` with `auth_code` |
| UNIONPAY | `800712` | WAP HK merchants | `/trade/v1/payment`, returns `pay_url` |
| UNIONPAY | `800714` | PC-Web HK merchants | `/trade/v1/payment`, returns `pay_url` |
| FPS | `802001` | MPM HK merchants | `/trade/v1/payment`, returns `qrcode` |
| FPS | `802010` | Merchant Presented App | `/trade/v1/payment`, returns `pay_params`/launch URL |
| Octopus | `803701` | Dynamic QRC MPM HK merchants | `/trade/v1/payment`, returns `qrcode` |
| Octopus | `803712` | WAP HK merchants | `/trade/v1/payment`, returns `pay_url` |
| Octopus | `803714` | PC-Web HK merchants | `/trade/v1/payment`, returns `pay_url` |
| Visa/Mastercard | `802801` | Online Payments | Hosted Checkout or Element SDK |
| Visa/Mastercard | `802808` | Offline Payments | POS SDK/card terminal |
| Apple Pay | `806527` | Online Payments | Hosted Checkout or Element SDK |
| UnionPay Card | `806708` | Offline Payments | POS SDK/card terminal |
| American Express | `806808` | Offline Payments | POS SDK/card terminal |

The official Payment Types page notes that `801101` transaction amount must be greater than 1 HKD.

The 4 pay types below appear on payment-specific pages but not in the official Payment Types master table. Confirm merchant enablement and current availability with QFPay before use.

| Channel | pay_type | Source page/scenario | Key requirement |
| --- | --- | --- | --- |
| Alipay | `800107` | Alipay Service Window H5 | Requires `openid` |
| WeChat Pay HK | `801008` | CPM direct settlement for HK merchants | Requires `auth_code` |
| PayMe | `805810` | In-App HK | App/wallet launch flow |
| UnionPay | `800710` | In-App | App/wallet launch flow |

## Payment Scenario Matrix

All rows below use `POST /trade/v1/payment` unless noted.

| Scenario | pay_type | Required extra fields | Response to use |
| --- | --- | --- | --- |
| Alipay MPM overseas | `800101` | Optional `expired_time`, `pay_tag`, `limit_pay` | `qrcode` |
| Alipay MPM HK | `801501` | Optional `expired_time`, `pay_tag`, `limit_pay` | `qrcode` |
| WeChat MPM / QR | `800201` | Optional `expired_time`; real-name `extend_info` if enabled | `qrcode` |
| PayMe MPM HK | `805801` | Common params | `qrcode` |
| UnionPay Quick Pass MPM | `800701` | Common params | `qrcode` |
| FPS MPM HK | `802001` | Common params | `qrcode` |
| Octopus Dynamic QR MPM HK | `803701` | Common params | `qrcode` |
| Generic CPM | `800008` | `auth_code` | Synchronous result or pending |
| Alipay CPM | `800108` | `auth_code` | Synchronous result or pending |
| WeChat CPM | `800208` | `auth_code` | Synchronous result or pending |
| WeChat Pay HK CPM direct settlement | `801008` | `auth_code` | Synchronous result or pending |
| PayMe CPM HK | `805808` | `auth_code` | Synchronous result or pending |
| UnionPay CPM | `800708` | `auth_code` | Synchronous result or pending |
| Alipay Web overseas | `801101` | Optional `return_url`, `pay_tag` | `pay_url` |
| Alipay Web HK | `801514` | Optional `return_url`, `pay_tag` | `pay_url` |
| WeChat Web QR HK | `800201` | Optional `expired_time` | `qrcode` |
| UnionPay Web HK | `800714` | Optional `return_url` | `pay_url` |
| PayMe Web HK | `805814` | Optional `return_url` | `pay_url` |
| Alipay WAP/H5 overseas | `801107` | Recommended `return_url`, `notify_url`, `goods_name` | `pay_url` |
| AlipayHK WAP | `801512` | Recommended `return_url`, `notify_url`, `goods_name` | `pay_url` |
| Alipay Service Window H5 | `800107` | `openid`, browser flow URLs | `pay_url` |
| WeChat H5 | `800212` | `extend_info.scene_info.h5_info`, `spbill_create_ip` | `pay_url` |
| UnionPay WAP HK | `800712` | Optional `return_url` | `pay_url` |
| PayMe WAP HK | `805812` | Optional `return_url`, `notify_url` | `pay_url` |
| Octopus WAP HK | `803712` | Recommended `return_url`, `notify_url` | `pay_url` |
| Octopus PC-Web HK | `803714` | Optional `return_url` | `pay_url` |
| WeChat JSAPI | `800207` | `sub_openid`; OAuth/openid flow first | `pay_params` |
| WeChat Mini Program | `800213` | `sub_openid` | `pay_params` |
| WeChat In-App | `800210` | Wallet SDK prerequisites; optional real-name `extend_info` | `pay_params` |
| Alipay In-App overseas | `801110` | `goods_name`, `return_url`; optional `seller_id` | `pay_params` |
| Alipay In-App HK | `801510` | `goods_name`, `return_url`; optional `seller_id` | `pay_params` |
| PayMe In-App HK | `805810` | Confirm enablement before use | `pay_params` or `pay_url` |
| UnionPay In-App | `800710` | Confirm enablement before use | `pay_params` or `pay_url` |
| FPS app-to-app | `802010` | Common params; launch returned URL in bank app | `pay_params` |
| Visa/Mastercard online | `802801` | Use Hosted Checkout or Element SDK | Checkout/Element result |
| Visa/Mastercard offline | `802808` | Usually POS SDK/card terminal flow | POS result |
| Apple Pay online | `806527` | Use Hosted Checkout or Element SDK | Checkout/Element result |
| UnionPay card offline | `806708` | Usually POS SDK/card terminal flow | POS result |
| American Express offline | `806808` | Usually POS SDK/card terminal flow | POS result |

`800107`, `801008`, `805810`, and `800710` come from payment-specific pages and are not in the official Payment Types master table. Confirm with QFPay before production use.

## Payment Flow Details

### MPM Dynamic QR

Use when the merchant displays a generated QR code and the customer scans it.

Required common fields: `txamt`, `txcurrcd`, `pay_type`, `out_trade_no`, `txdtm`; include `mchid` only if assigned. Optional fields include `expired_time`, `goods_name`, `pay_tag`, `limit_pay`, `notify_url`, `udid`.

Return handling: render `qrcode` as a scannable QR image. Store `syssn`. Confirm final status through async notification and/or `/trade/v1/query`.

### CPM Customer Barcode

Use when a customer is present and shows a wallet barcode/QR to a cashier or POS scanner.

Required extra field: `auth_code`. It is one-time use and must be captured in real time.

Return handling:

- `0000`: payment successful.
- `1143` or `1145`: customer/password/channel processing. Do not resubmit a new payment immediately; query final status.
- Other codes: failed unless enquiry proves otherwise.

### Web Payment

Use for desktop or browser checkout QR flows. Pay types include WeChat Web QR `800201`, Alipay Web `801101`/`801514`, UnionPay Web `800714`, PayMe Web `805814`, and Octopus PC-Web `803714`.

Return handling: use `pay_url` or `qrcode` depending on wallet. For AlipayHK Web, QFPay notes that merchants commonly embed the returned QR/payment URL in the merchant page or an iframe.

### WAP/H5 Payment

Use in mobile browsers such as Safari, Chrome, or Edge. Avoid relying on social app in-app browsers because external wallet invocation may be blocked.

Common pay types include WeChat H5 `800212`, Alipay WAP `801107`/`801512`, UnionPay WAP `800712`, PayMe WAP `805812`, and Octopus WAP `803712`.

Recommended fields: `return_url` for customer redirect and `notify_url` for backend confirmation. Always verify final result server-side; frontend redirects are not enough.

WeChat H5 (`800212`) requires `extend_info`:

```json
{
  "scene_info": {
    "h5_info": {
      "type": "Wap",
      "wap_url": "https://merchant.example/mobile-pay",
      "wap_name": "Merchant"
    }
  },
  "spbill_create_ip": "203.0.113.10"
}
```

Send `extend_info` as a compact JSON string in the form body and sign that exact string.

### WeChat JSAPI

Use only inside the WeChat in-app browser. Do not use JSAPI in Chrome/Safari.

Flow:

1. Open `GET /tool/v1/get_weixin_oauth_code` inside WeChat. Send `app_code`, `redirect_uri`, optional `mchid`, and `sign` as query parameters.
2. Exchange the returned OAuth code via `GET /tool/v1/get_weixin_openid` with signed headers.
3. Create payment using `POST /trade/v1/payment`, `pay_type=800207`, `sub_openid=<openid>`, and common params.
4. Pass `pay_params` to WeChat JSAPI or redirect to QFPay's documented direct payment module.
5. Query or handle callback for final status.

Do not cache or reuse OAuth codes or openid values for later payment attempts unless QFPay/WeChat explicitly approves that architecture.

### WeChat Mini Program

Use `pay_type=800213`. Obtain `sub_openid` through the Mini Program flow, then call `/trade/v1/payment`. Pass returned `pay_params` into `wx.requestPayment`.

Optional fields include `expired_time`, `limit_pay`, and real-name `extend_info` if enabled.

### WeChat In-App

Use `pay_type=800210` for native mobile apps using WeChat SDK. Prerequisites include WeChat Open Platform app registration, AppID, and QFPay onboarding/approval. Response `pay_params` contains WeChat SDK fields such as `appid`, `partnerid`, `prepayid`, `package`, `noncestr`, `timestamp`, and `sign`.

### Alipay In-App

Use `pay_type=801110` for Alipay CN/overseas settlement or `801510` for AlipayHK/QFPay settlement. Required fields include common params plus `goods_name` and `return_url`. Optional fields include `goods_info`, `pay_tag`, `expired_time`, `seller_id`, and `mchid`.

Pass returned `pay_params` into the Alipay SDK exactly as returned. When constructing Alipay `orderInfo`, sort fields as the Alipay SDK requires and place `sign`/`sign_type` at the end.

### FPS App-To-App

Use `pay_type=802010`. Retrieve `pay_params` from `/trade/v1/payment`, then launch the FPS bank app:

- Android native: send an `Intent` action such as `hk.com.hkicl` with the returned URL.
- iOS native: use `UIActivityViewController`/extension with type identifier `hk.com.hkicl`.
- H5-in-app: use JSBridge to pass the returned URL to native code.

Always verify the final result via backend query or callback.

## Hosted Checkout

Use Hosted Checkout when the merchant wants QFPay to render the payment page and payment-method selection.

Endpoint: `GET https://<base-url>/checkstand/#/?<signed query>`.

Parameters:

| Field | Required | Notes |
| --- | --- | --- |
| `appcode` | Yes | Store identifier. This is not `X-QF-APPCODE`. |
| `sign_type` | Yes | `SHA256` recommended; `MD5` supported. |
| `sign` | Yes | Signature appended after signing the other query params. |
| `paysource` | Yes | Must end with `_checkout`, e.g. `remotepay_checkout`. |
| `txamt` | Yes | Amount in cents. |
| `txcurrcd` | Yes | Currency code. |
| `out_trade_no` | Yes | Unique merchant order ID. |
| `txdtm` | Yes | `YYYY-MM-DD HH:mm:ss`. |
| `return_url` | Yes | Success redirect. |
| `failed_url` | Yes | Failure redirect. |
| `notify_url` | Yes | Backend callback. |
| `mchntid` | Agent scenarios | Hosted Checkout uses `mchntid`, not `mchid`. |
| `goods_name` | No | Product name. |
| `udid` | No | Device identifier. |
| `expired_time` | No | QR expiry 5-120 min where supported. |
| `checkout_expired_time` | No | Checkout session expiry. |
| `limit_pay` | No | `no_credit` disables credit cards. |
| `lang` | No | `zh-hk`, `zh-cn`, or `en`. |
| `cancel_url` | No | Redirect when customer cancels. |

Generate Hosted Checkout signatures server-side. Never put `client_key` in frontend code.

## Element SDK

Use Element SDK when the merchant wants embedded QFPay-hosted payment UI components for cards and wallets.

Backend:

- Endpoint: `POST /payment_element/v1/create_payment_intent`.
- Headers: `X-QF-APPCODE`, `X-QF-SIGN`.
- Parameters: `txamt` required, `pay_type` required, `out_trade_no` required, `txcurrcd` optional, `mchid` optional/agent, `return_url`, `failed_url`, `notify_url`.
- Response includes `payment_intent` and `intent_expiry`.

Frontend:

1. Load environment-specific `qfpay.js`: QA/Sandbox `https://cdn-int.qfapi.com/qfpay_element/qfpay.js`, live-testing `https://test-cdn-hk.qfapi.com/qfpay_element/qfpay.js`, or production `https://cdn-hk.qfapi.com/qfpay_element/qfpay.js`.
2. Configure with `QFpay.config({ region: "hk", env: "prod" | "test" | "qa" })`.
3. Render with `qfpay.element().create(...)` for card-only or `createEnhance(...)` for wallet+card.
4. Initiate with `payment.pay(...)` for card or `payment.walletPay(...)` for wallet flows.
5. Confirm with `qfpay.confirmPayment(...)` or `qfpay.confirmWalletPayment(...)`.
6. Query with `payment.inquiry(...)` or backend `/trade/v1/query`.

Do not place the Element container inside a `<form>` element. Create intents and signatures on the backend.

## Query

Endpoint: `POST /trade/v1/query`.

Use for payments, refunds, reversals, close outcomes, reconciliation, and uncertain states.

Parameters:

| Field | Required | Notes |
| --- | --- | --- |
| `mchid` | Conditional | Required if assigned to the merchant or used on the original payment. |
| `syssn` | No | QFPay transaction number(s), comma-separated. Prefer this when available. |
| `out_trade_no` | No | Merchant order number(s), comma-separated. Use if payment did not return `syssn`. |
| `pay_type` | No | Payment types, comma-separated. |
| `respcd` | No | Filter by result code. |
| `start_time` | No/conditional | `YYYY-MM-DD HH:mm:ss`. Required for cross-month queries. |
| `end_time` | No/conditional | `YYYY-MM-DD HH:mm:ss`. Required for cross-month queries. |
| `page` | No | Default 1. |
| `page_size` | No | Default 10, max 100. |

Rules:

- Query by `syssn` when available.
- Use `out_trade_no` when the original call did not return `syssn`.
- For cross-month queries, provide `start_time` and `end_time`. QFPay notes the time range must not cross month boundaries in some docs; split ranges by month if needed.
- Refund query results may include `origssn`, the original payment `syssn`.

## Refund

Endpoint: `POST /trade/v1/refund`.

Use only when the original payment is successful. For credit-card payments, QFPay handles same-day refund as a void through the same refund API.

Parameters:

| Field | Required | Notes |
| --- | --- | --- |
| `syssn` | Yes | Original payment QFPay transaction number. In the refund response, `syssn` is the new refund transaction number. |
| `out_trade_no` | Yes | Unique merchant refund order ID. Do not reuse payment order ID unless QFPay explicitly allows it. |
| `txamt` | Yes | Refund amount in cents. Must not exceed refundable amount. |
| `txdtm` | Yes | Refund request time, `YYYY-MM-DD HH:mm:ss`. |
| `mchid` | Conditional | Include only if assigned/required. |
| `udid` | No | Device identifier. |

Response fields commonly include `syssn` (refund transaction), `orig_syssn`, `txamt`, `sysdtm`, `respcd`, `resperr`, and cash/refund currency fields.

Handling:

- `0000`: refund successful or accepted as successful by API response. Persist refund `syssn` and query if reconciliation requires final confirmation.
- `1143` or `1145`: processing. Query `/trade/v1/query`.
- Other codes: failed. Do not retry with a different `out_trade_no` until original refund status is known.

## Reversal And Close

### Reversal

Endpoint: `POST /trade/v1/reversal`.

Use cases:

- Incomplete QR transactions, such as QR scanned but payment abandoned or CPM pending password confirmation.
- Online Credit Card / Apple Pay authorised transactions as a real-time void.

Supported documented reversal pay types:

- QR incomplete: Alipay MPM `800101`, Alipay MPM HK `801501`, WeChat MPM `800201`, Alipay CPM `800108`.
- Card/Apple authorised void: Visa/Mastercard `802801`, Apple Pay `806527`.

Do not use reversal to refund a successful QR payment. Use `/trade/v1/refund`.

Parameters:

| Field | Required | Notes |
| --- | --- | --- |
| `mchid` | Conditional | Required only for agent/specific configurations. |
| `syssn` | Yes* | QFPay transaction number to reverse. |
| `out_trade_no` | Yes* | Merchant order number to reverse. |
| `txamt` | Yes | Original transaction amount in cents. |
| `txdtm` | Yes | Original transaction time, `YYYY-MM-DD HH:mm:ss`. |
| `udid` | No | Device identifier. |

At least one of `syssn` or `out_trade_no` must be provided.

Handling:

- `0000`: reversal/cancel successful.
- `1143` or `1145`: reversal/cancel processing. Poll `/trade/v1/query`.
- Other codes: failed or not operable. Query original order before taking a second action.

### Close

Endpoint documented under reversal page: `GET /trade/v1/close`.

Use where QFPay documents close instead of reversal, especially selected WeChat CPM flows:

- `800008` generic CPM for WeChat.
- `800208` WeChat CPM.
- `801008` WeChat Pay HK CPM direct settlement.

Parameters match reversal-style identifiers: optional/conditional `mchid`, `syssn` or `out_trade_no`, `txamt`, `txdtm`, and optional `udid`.

## Preauthorisation

Use preauthorisation when the final capture amount is unknown up front, such as hotels, rentals, delayed shipment, or variable-price services.

Create the preauthorised transaction through Payment Element SDK. No funds are captured at this stage.

Capture funds:

- Endpoint: `POST /trade/v1/authtrade`.
- Required: `txamt`, `syssn` of the original preauth order.
- Optional/conditional: `txcurrcd`, `mchid`.
- Multiple partial captures are allowed if total capture does not exceed authorised amount.

Unfreeze remaining funds:

- Endpoint: `POST /trade/v1/unfreeze`.
- Required: `txamt`, `txdtm`, original preauth `syssn`, original `out_trade_no`.
- Optional/conditional: `mchid`.
- Unfreeze can be done only once. After unfreeze, no further capture can be made.

Captured payment refund:

- Use `/trade/v1/refund`.
- Use the capture step `syssn`, not the original preauthorisation `syssn`.

Capture windows documented by QFPay:

- General merchants: up to 7 days.
- Hotels/rentals: up to 28 days.
- Actual window depends on agreement and channel capability.

## Async Notifications

QFPay can POST successful payment/refund notifications to the merchant callback URL.

Rules:

- Configure the callback URL with QFPay support, including merchant/store information.
- Standard callback method: `POST`, `Content-Type: application/json`.
- Allowed callback ports: 80 and 443.
- One `app_code` + `client_key` pair can bind to one notification URL. Agents should use a shared endpoint for sub-merchants.
- QFPay retries if it does not receive HTTP `200` and body `SUCCESS`: approximately 2 min, 10 min, 10 min, 60 min, 2 hours, 6 hours, 15 hours.
- Notification IPs documented: `13.228.112.115`, `18.138.115.47`, `18.166.202.92`.

Verification:

```python
import hashlib

def verify_qfpay_callback(raw_body: bytes, client_key: str, signature: str) -> bool:
    expected = hashlib.md5(raw_body + client_key.encode("utf-8")).hexdigest().upper()
    return expected == signature.upper()
```

Common callback fields:

| Field | Meaning |
| --- | --- |
| `status` | `1` means payment successful. |
| `notify_type` | `payment`, `refund`, or for preauth `unfreeze` where documented. |
| `pay_type` | Payment method code. |
| `syssn` | QFPay transaction number. |
| `out_trade_no` | Merchant order number. |
| `txamt` | Amount in cents. |
| `txcurrcd` | Currency code. |
| `txdtm` | Merchant transaction time. |
| `sysdtm` | QFPay system time and settlement cutoff reference. |
| `paydtm` | Payment completion time. |
| `cancel` | Cancellation/refund marker. |
| `respcd` | Usually `0000` in successful notifications. |

`cancel` values:

| Value | Meaning |
| --- | --- |
| `0` | Not cancelled. |
| `1` | CPM reversed or refunded. |
| `2` | MPM cancelled. |
| `3` | Refunded. |
| `4` | Preauth order completed (Alipay). |
| `5` | Partially refunded. |

Always process callbacks idempotently by `syssn` and `out_trade_no`. Query if signature verification fails, callback is delayed, or local state conflicts.

## Status Codes And Retry Policy

Core result handling:

| Code | Meaning | Action |
| --- | --- | --- |
| `0000` | Transaction/API success | Persist IDs. For user-driven payment flows, still rely on callback/query for final confirmation. |
| `1143` | Order not paid yet or customer entering password | Do not create a new order. Query after delay. |
| `1145` | Transaction processing | Do not create a new order. Query after delay. |
| `1298` | Network delay; payment may have completed | Do not retry payment immediately. Query first. |
| `1108` | Signature error | Rebuild canonical string and verify credentials/env. |
| `2011` | Transaction serial number repeats | Query by `out_trade_no`; do not issue a new payment unless intentional. |
| `1125`, `1262` | Already refunded | Query refund/original order and reconcile. |
| `1260` | Already paid | Treat as state conflict; query and reconcile. |
| `1261` | Not paid | For refund/cancel, action is not valid yet. Query original. |
| `1263`, `1264` | Already cancelled/closed | Query and reconcile. |
| `1266`, `1267` | Amount/order information mismatch | Stop and verify local order data. |
| `1268` | Order does not exist | Verify identifiers, merchant, and time window. |
| `1270`, `1271` | Partial refund not supported | Fall back to full refund only if business-approved. |
| `1272` | Refund amount exceeds refundable limit | Query refundable state; correct amount. |
| `1294` | Risk control / bank prohibited | Do not automatic-retry. Surface to operator/customer. |
| `1295`, `1296` | Network congestion | Retry with backoff only when safe and idempotent. |
| HTTP `429` | Rate limit exceeded | Back off. QFPay documents 100 RPS and 400 requests/min per merchant. |

Retry policy:

1. Prefer querying before retrying any money-moving action.
2. Use the same `out_trade_no` for idempotent retry of the same intended transaction.
3. Never switch to a new `out_trade_no` to "fix" a pending payment, refund, reversal, or close unless the user explicitly wants a separate transaction.
4. Use exponential backoff for 429 and network congestion.
5. Log complete responses, but redact secrets and sensitive customer/card fields.

## Android App-To-App POS SDK

Use the App Call App Android SDK when a third-party Android POS app invokes the QFPay HaoJin app locally instead of calling OpenAPI directly.

Setup:

- Require HaoJin app installed.
- Add Android permission: `com.qfpay.haojin.permission.OPEN_API`.
- Include the SDK JAR, currently documented as version `2.3.4.jar`.
- Set target app ID: `Config.setTargetAppId("in.haojin.nearbymerchant.oversea")`.
- Create API instance: `TradeApiFactory.createTradeApi(activity, callback)`.

Operations:

| Operation | Request class / method |
| --- | --- |
| Collection/payment | `new CollectionReq(amount)` then `mTradeApi.doTrade(req)` |
| Scan customer code | `req.setScan_type(CollectionReq.SCAN_TYPE_SCAN)` |
| Display QR code | `req.setScan_type(CollectionReq.SCAN_TYPE_QRCODE)` |
| Refund | `new RefundReq(qfOrderId)` |
| Query list | `new GetTransListReq()` with channel/type/month/time/page setters |
| Query detail | `new GetTransReq(qfOrderId)` and optional `setOut_trade_no(...)` |
| Transaction summary | `new CheckTradeSumReq()` |
| User configuration | `new GetUserConfigReq()` |
| Preauth capture | `new PreAuthTransDeductReq(transId)` |
| Preauth cancel | `new PreAuthTransCancelReq(transId)` |
| Preauth list | `new PreAuthTransListReq(pageSize, pageNum)` |
| Preauth detail | `new PreAuthTransDetailReq(transId)` |
| Card refund | `new CardRefundReq(qfOrderId)` |
| Card settlement | `new CardSettleReq()` |

Always null-check parsed SDK responses. QFPay documents that `parseResponse(...)` can return null.
