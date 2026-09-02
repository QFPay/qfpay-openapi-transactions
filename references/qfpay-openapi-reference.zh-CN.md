# QFPay OpenAPI 中文参考

整理日期：2026-09-02。生产上线前仍需以 QFPay 当前官方文档和商户开通配置为准。

官方来源：

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
- https://sdk.qfapi.com/integration/online-shop/checkout-integration/checkout
- https://sdk.qfapi.com/integration/online-shop/checkout-integration/payment-element
- https://sdk.qfapi.com/integration/common-api/transaction-enquiry
- https://sdk.qfapi.com/integration/common-api/refund
- https://sdk.qfapi.com/integration/common-api/reversal
- https://sdk.qfapi.com/integration/common-api/async-notifications
- https://sdk.qfapi.com/integration/online-shop/integration-by-use-case/preauth
- https://sdk.qfapi.com/integration/in-store/pos-api/app-call-app

## 目录

- 环境和凭证
- 签名
- 通用支付参数
- 支付场景和 pay_type
- 各类下单流程
- Hosted Checkout
- Element SDK
- 交易查询
- 退款
- 冲正和 close
- 预授权
- 异步通知
- 状态码和重试策略
- Android App-to-App POS SDK

## 环境和凭证

本集成只使用以下三个 base URL，除非 QFPay 明确发放商户专用 endpoint：

| 业务名称 | 官方英文名 | Base URL | 用途 |
| --- | --- | --- | --- |
| QA | Sandbox | `https://openapi-int.qfapi.com` | 模拟交易、开发、联调。不会扣真实资金。 |
| 线上测试 | Live Testing | `https://test-openapi-hk.qfapi.com` | 用测试账号跑真实支付流程，不结算。如果使用真实支付方式测试，应立即退款。 |
| 生产 | Production | `https://openapi-hk.qfapi.com` | 真实交易、真实结算、对账。 |

不要使用旧示例或泛化示例里的 `https://api.qfapi.com`。

凭证：

| 名称 | 说明 |
| --- | --- |
| `app_code` | 门店标识。标准 API 请求头传 `X-QF-APPCODE`。 |
| `client_key` | 签名密钥。只能放服务端或安全密钥管理系统。 |
| `mchid` | 可选商户/门店标识。只有 QFPay 发放或通道要求时才传；未发放时请求参数和签名串都不要包含。 |

环境和凭证必须匹配。QA、线上测试、生产的凭证和域名混用通常会导致认证或签名错误。

凭据安全规则：

- 把 `app_code` 视为敏感商户标识，把 `client_key` 视为密钥。
- 不要把真实 `client_key` 放进前端、移动端、仓库、issue、PR、日志、截图或最终回复。
- 不要在命令行参数里明文传 `client_key`；优先使用无回显输入、环境变量或密钥管理系统。
- `X-QF-SIGN` 和 Hosted Checkout `sign` 可授权同一组参数请求，按敏感信息脱敏。
- 发现凭证泄漏时，停止资金动作，轮换 `client_key`，再恢复调用。

## 签名

标准 API 签名流程：

1. 删除 `null` 和空字符串参数。
2. 按参数名 ASCII 升序排序。
3. 组装为 `key=value`，用 `&` 连接。
4. 末尾直接追加 `client_key`，不加分隔符。
5. 默认 MD5；使用 SHA256 时按同样原文 hash。
6. digest 转大写。
7. 请求头传 `X-QF-SIGN`；SHA256 时额外传 `X-QF-SIGNTYPE: SHA256`。

Python 示例：

```python
import hashlib

def qfpay_sign(params, client_key, sign_type="MD5"):
    clean = {k: str(v) for k, v in params.items() if v is not None and str(v) != ""}
    canonical = "&".join(f"{k}={clean[k]}" for k in sorted(clean))
    raw = (canonical + client_key).encode("utf-8")
    if sign_type.upper() == "SHA256":
        return hashlib.sha256(raw).hexdigest().upper()
    return hashlib.md5(raw).hexdigest().upper()
```

注意：

- 签名参数必须和实际发送参数一致。
- 不要签 `X-QF-SIGN`、`sign`、空字段、null 字段。
- 参数名和值大小写敏感。
- 使用 UTF-8。
- `extend_info` 等对象字段建议转为无多余空格的 JSON 字符串，签名时用实际发送的那个字符串。
- Hosted Checkout 的 `sign` 是 query 参数，不能参与签名原文。
- 回调验签用「原始 JSON body + `client_key`」做 MD5，不按字段排序。

## 通用支付参数

大多数 `POST /trade/v1/payment` 共享这些参数：

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `txamt` | 是 | Int | 金额，单位为最小币值单位，例如 `100` = 1.00。QFPay 建议大于 200，降低风控失败概率。 |
| `txcurrcd` | 是 | String(3) | ISO 4217 币种，例如 `HKD`。部分支付方式只支持 HKD。 |
| `pay_type` | 是 | String(6) | 支付方式代码。必须确认商户已开通。 |
| `out_trade_no` | 是 | String(128) | 商户订单号。同一商户下支付和退款请求都必须唯一。 |
| `txdtm` | 是 | String(20) | `YYYY-MM-DD HH:mm:ss`。 |
| `auth_code` | CPM 必填 | String(128) | 用户钱包付款码/授权码。一次性、实时采集。 |
| `expired_time` | MPM/链接支付可选 | String(3) | 二维码或支付链接过期分钟数，默认 30，通常范围 5-120。 |
| `goods_name` | 通常可选，App 支付常必填 | String(64) | 商品名。某些通道要求不超过 20 个字母数字字符；中文用 UTF-8。 |
| `mchid` | 条件必填 | String(16) | QFPay 发放或通道要求时才传。 |
| `udid` | 否 | String(40) | 设备标识，用于后台展示和追踪。 |
| `notify_url` | 推荐 | String | 后端异步通知地址。 |
| `return_url` | 浏览器/App 场景常用 | String | 支付完成后的用户跳转地址或 deep link。 |
| `extend_info` | 条件必填 | JSON 字符串 | 通道扩展字段，例如 WeChat H5 场景信息、实名信息。 |
| `limit_pay` | 否 | String | `no_credit` 表示禁用信用卡，适用范围看通道。 |
| `pay_tag` | Alipay 可选 | String(16) | 默认 `ALIPAYHK`；大陆支付宝可用 `ALIPAYCN`。 |

QFPay 文档列出的币种：`AED`、`CNY`、`EUR`、`HKD`、`IDR`、`JPY`、`MMK`、`MYR`、`SGD`、`THB`、`USD`、`CAD`、`AUD`。

## 支付场景和 pay_type

以下场景默认使用 `POST /trade/v1/payment`。

| 场景 | pay_type | 额外参数 | 返回重点 |
| --- | --- | --- | --- |
| 支付宝 MPM 海外 | `800101` | 可选 `expired_time`、`pay_tag`、`limit_pay` | `qrcode` |
| 支付宝 MPM 香港 | `801501` | 可选 `expired_time`、`pay_tag`、`limit_pay` | `qrcode` |
| 微信 MPM / QR | `800201` | 可选 `expired_time`；实名时传 `extend_info` | `qrcode` |
| PayMe MPM 香港 | `805801` | 通用参数 | `qrcode` |
| 银联 Quick Pass MPM | `800701` | 通用参数 | `qrcode` |
| FPS MPM 香港 | `802001` | 通用参数 | `qrcode` |
| Octopus 动态码 MPM 香港 | `803701` | 通用参数 | `qrcode` |
| 泛 CPM | `800008` | `auth_code` | 同步结果或处理中 |
| 支付宝 CPM | `800108` | `auth_code` | 同步结果或处理中 |
| 微信 CPM | `800208` | `auth_code` | 同步结果或处理中 |
| WeChat Pay HK CPM 直清 | `801008` | `auth_code` | 同步结果或处理中 |
| PayMe CPM 香港 | `805808` | `auth_code` | 同步结果或处理中 |
| 银联 CPM | `800708` | `auth_code` | 同步结果或处理中 |
| 支付宝 Web 海外 | `801101` | 可选 `return_url`、`pay_tag` | `pay_url` |
| 支付宝 Web 香港 | `801514` | 可选 `return_url`、`pay_tag` | `pay_url` |
| 微信 Web QR 香港 | `800201` | 可选 `expired_time` | `qrcode` |
| 银联 Web 香港 | `800714` | 可选 `return_url` | `pay_url` |
| PayMe Web 香港 | `805814` | 可选 `return_url` | `pay_url` |
| 支付宝 WAP/H5 海外 | `801107` | 推荐 `return_url`、`notify_url`、`goods_name` | `pay_url` |
| 支付宝香港 WAP | `801512` | 推荐 `return_url`、`notify_url`、`goods_name` | `pay_url` |
| 支付宝 Service Window H5 | `800107` | `openid`、浏览器跳转参数 | `pay_url` |
| 微信 H5 | `800212` | `extend_info.scene_info.h5_info`、`spbill_create_ip` | `pay_url` |
| 银联 WAP 香港 | `800712` | 可选 `return_url` | `pay_url` |
| PayMe WAP 香港 | `805812` | 可选 `return_url`、`notify_url` | `pay_url` |
| 微信 JSAPI | `800207` | 先 OAuth 拿 `sub_openid` | `pay_params` |
| 微信小程序 | `800213` | `sub_openid` | `pay_params` |
| 微信 In-App | `800210` | 微信开放平台和 SDK 前置配置 | `pay_params` |
| 支付宝 In-App 海外 | `801110` | `goods_name`、`return_url`，可选 `seller_id` | `pay_params` |
| 支付宝 In-App 香港 | `801510` | `goods_name`、`return_url`，可选 `seller_id` | `pay_params` |
| FPS App-to-App | `802010` | 通用参数；用返回 URL 拉起银行 App | `pay_params` |
| Visa/Mastercard Online | `802801` | 使用 Hosted Checkout 或 Element SDK | Checkout/Element 结果 |
| Visa/Mastercard Offline | `802808` | 通常是 POS SDK/卡终端流程 | POS 结果 |
| Apple Pay Online | `806527` | 使用 Hosted Checkout 或 Element SDK | Checkout/Element 结果 |
| 银联卡 Offline | `806708` | 通常是 POS SDK/卡终端流程 | POS 结果 |
| American Express Offline | `806808` | 通常是 POS SDK/卡终端流程 | POS 结果 |

In-App use-case 页面还提到 `805810` PayMe In-App 和 `800710` UnionPay In-App。使用前必须向 QFPay 确认商户是否开通。

## 各类下单流程

### MPM 动态二维码

商户生成二维码，用户扫码付款。典型场景包括 POS 屏幕、自助机、网页显示二维码。

必填通用字段：`txamt`、`txcurrcd`、`pay_type`、`out_trade_no`、`txdtm`。按配置决定是否传 `mchid`。可选 `expired_time`、`goods_name`、`pay_tag`、`limit_pay`、`notify_url`、`udid`。

返回后把 `qrcode` 渲染成可扫码图片，保存 `syssn`。最终状态通过异步通知和/或 `/trade/v1/query` 确认。

### CPM 用户付款码

用户到店出示钱包付款码，商户扫码发起扣款。必须实时采集 `auth_code`。

返回处理：

- `0000`：支付成功。
- `1143` 或 `1145`：用户输密、钱包确认或通道处理中。不要重下单，延迟后查询。
- 其他：按失败处理，除非查询证明已有最终成功状态。

### Web 支付

用于桌面或普通浏览器收银台。常见 pay_type：微信 Web QR `800201`、支付宝 Web `801101`/`801514`、银联 Web `800714`、PayMe Web `805814`。

返回可能是 `pay_url` 或 `qrcode`。支付宝香港 Web 通常把返回的二维码/支付 URL 嵌入商户页面或 iframe。

### WAP/H5 支付

用于 Safari、Chrome、Edge 等手机浏览器。不要依赖社交 App 内置浏览器，因为外部钱包拉起可能被限制。

建议传 `return_url` 做用户跳转，传 `notify_url` 做后端确认。前端跳转结果不能作为最终支付结果。

微信 H5 `800212` 必须传 `extend_info`：

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

实际请求中把 `extend_info` 作为紧凑 JSON 字符串放入 form body，并用同一个字符串签名。

### 微信 JSAPI

只在微信内置浏览器中使用，Chrome/Safari 不适用。

流程：

1. 在微信内打开 `GET /tool/v1/get_weixin_oauth_code`。`app_code`、`redirect_uri`、可选 `mchid`、`sign` 用 query 参数传，不用请求头。
2. 用返回的 OAuth code 调 `GET /tool/v1/get_weixin_openid`，请求头带 `X-QF-APPCODE` 和 `X-QF-SIGN`。
3. 调 `POST /trade/v1/payment`，`pay_type=800207`，传 `sub_openid=<openid>` 和通用参数。
4. 把 `pay_params` 交给 WeChat JSAPI，或按 QFPay 文档跳转到 direct payment module。
5. 用回调或 `/trade/v1/query` 确认最终状态。

OAuth code 和 openid 不要缓存复用，除非 QFPay/微信明确批准对应架构。

### 微信小程序

使用 `pay_type=800213`。小程序侧获取 `sub_openid`，服务端调用 `/trade/v1/payment`，再把返回 `pay_params` 传给 `wx.requestPayment`。

可选参数包括 `expired_time`、`limit_pay` 和实名 `extend_info`。

### 微信 In-App

使用 `pay_type=800210`。前置条件包括微信开放平台注册 App、取得 AppID、完成 QFPay 开通审批。返回 `pay_params`，字段通常包括 `appid`、`partnerid`、`prepayid`、`package`、`noncestr`、`timestamp`、`sign`，传给微信 SDK。

### 支付宝 In-App

使用 `pay_type=801110`（Alipay CN/海外结算）或 `801510`（AlipayHK/QFPay 结算）。必填通用参数，并额外传 `goods_name` 和 `return_url`。可选 `goods_info`、`pay_tag`、`expired_time`、`seller_id`、`mchid`。

把 QFPay 返回的 `pay_params` 按支付宝 SDK 要求组装 `orderInfo`。字段名和值按返回内容保持一致；支付宝 SDK 的 `sign`、`sign_type` 放末尾。

### FPS App-To-App

使用 `pay_type=802010`。先调用 `/trade/v1/payment` 获取 `pay_params`，再拉起银行 App。

- Android native：用 `Intent`，action 类似 `hk.com.hkicl`，把返回 URL 放入 intent。
- iOS native：用 `UIActivityViewController`/extension，type identifier 为 `hk.com.hkicl`。
- H5-in-app：H5 通过 JSBridge 把返回 URL 传给 native。

最终状态必须由后端查询或回调确认。

## Hosted Checkout

适合让 QFPay 托管收银台和支付方式选择页面。

入口：`GET https://<base-url>/checkstand/#/?<signed query>`。

参数：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `appcode` | 是 | 门店标识。这里不是 `X-QF-APPCODE`。 |
| `sign_type` | 是 | 推荐 `SHA256`，也支持 `MD5`。 |
| `sign` | 是 | 先签除 `sign` 外的 query 参数，再追加。 |
| `paysource` | 是 | 必须以 `_checkout` 结尾，例如 `remotepay_checkout`。 |
| `txamt` | 是 | 金额，单位分。 |
| `txcurrcd` | 是 | 币种。 |
| `out_trade_no` | 是 | 商户唯一订单号。 |
| `txdtm` | 是 | `YYYY-MM-DD HH:mm:ss`。 |
| `return_url` | 是 | 成功跳转。 |
| `failed_url` | 是 | 失败跳转。 |
| `notify_url` | 是 | 后端回调。 |
| `mchntid` | 代理场景 | Hosted Checkout 使用 `mchntid`，不是 `mchid`。 |
| `goods_name` | 否 | 商品名。 |
| `udid` | 否 | 设备标识。 |
| `expired_time` | 否 | 二维码过期时间，通常 5-120 分钟。 |
| `checkout_expired_time` | 否 | 收银台会话过期时间。 |
| `limit_pay` | 否 | `no_credit` 禁用信用卡。 |
| `lang` | 否 | `zh-hk`、`zh-cn`、`en`。 |
| `cancel_url` | 否 | 用户取消后的跳转。 |

签名必须在服务端生成，不要把 `client_key` 放在前端。

## Element SDK

适合在商户页面嵌入 QFPay 托管的卡表单/钱包组件。

后端：

- Endpoint：`POST /payment_element/v1/create_payment_intent`。
- Headers：`X-QF-APPCODE`、`X-QF-SIGN`。
- 参数：`txamt` 必填、`pay_type` 必填、`out_trade_no` 必填；`txcurrcd` 可选；`mchid` 按配置；可传 `return_url`、`failed_url`、`notify_url`。
- 返回：`payment_intent`、`intent_expiry` 等。

前端：

1. 按环境加载 `qfpay.js`：QA/Sandbox 用 `https://cdn-int.qfapi.com/qfpay_element/qfpay.js`，线上测试用 `https://test-cdn-hk.qfapi.com/qfpay_element/qfpay.js`，生产用 `https://cdn-hk.qfapi.com/qfpay_element/qfpay.js`。
2. `QFpay.config({ region: "hk", env: "prod" | "test" | "qa" })` 初始化。
3. `qfpay.element().create(...)` 渲染卡表单，或 `createEnhance(...)` 渲染钱包+卡。
4. 卡支付用 `payment.pay(...)`；钱包支付用 `payment.walletPay(...)`。
5. 用 `qfpay.confirmPayment(...)` 或 `qfpay.confirmWalletPayment(...)` 确认。
6. 用 `payment.inquiry(...)` 或后端 `/trade/v1/query` 查询。

Element 容器不要放在 `<form>` 里面，否则可能渲染失败。Intent 创建和签名都应在后端完成。

## 交易查询

Endpoint：`POST /trade/v1/query`。

用途：查支付、退款、冲正、close 结果、对账、处理中状态、异常恢复。

参数：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `mchid` | 条件必填 | 原交易/商户配置要求时传。 |
| `syssn` | 否 | QFPay 交易号，可逗号分隔多个。可用时优先用它。 |
| `out_trade_no` | 否 | 商户订单号，可逗号分隔多个。原交易没返回 `syssn` 时使用。 |
| `pay_type` | 否 | 支付方式，可逗号分隔。 |
| `respcd` | 否 | 按结果码过滤。 |
| `start_time` | 条件必填 | `YYYY-MM-DD HH:mm:ss`。跨月查询需要。 |
| `end_time` | 条件必填 | `YYYY-MM-DD HH:mm:ss`。跨月查询需要。 |
| `page` | 否 | 默认 1。 |
| `page_size` | 否 | 默认 10，最大 100。 |

规则：

- 有 `syssn` 时优先用 `syssn` 查。
- 没有 `syssn` 时用 `out_trade_no` 查。
- 跨月查询提供 `start_time` 和 `end_time`；部分文档提示时间区间不能跨月，必要时按月拆分。
- 查询退款交易时，结果可能包含 `origssn`，表示原支付交易 `syssn`。

## 退款

Endpoint：`POST /trade/v1/refund`。

只对成功支付交易使用。信用卡同日退款通常由 QFPay 通过同一退款 API 按 void 处理。

参数：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `syssn` | 是 | 原支付 QFPay 交易号。注意退款响应里的 `syssn` 是新退款交易号。 |
| `out_trade_no` | 是 | 商户退款单号。必须唯一，不要随意复用支付单号。 |
| `txamt` | 是 | 退款金额，单位分，不得超过可退金额。 |
| `txdtm` | 是 | 退款请求时间，`YYYY-MM-DD HH:mm:ss`。 |
| `mchid` | 条件必填 | QFPay 发放或通道要求时才传。 |
| `udid` | 否 | 设备标识。 |

常见响应字段：`syssn`（退款交易号）、`orig_syssn`、`txamt`、`sysdtm`、`respcd`、`resperr`、`cash_fee`、`cash_fee_type`、`cash_refund_fee`、`cash_refund_fee_type`。

处理：

- `0000`：退款成功或 API 返回成功。保存退款 `syssn`，必要时查询确认。
- `1143` 或 `1145`：处理中。调用 `/trade/v1/query`。
- 其他：失败。不要换新退款单号重试，先查原退款状态。

## 冲正和 close

### 冲正 reversal

Endpoint：`POST /trade/v1/reversal`。

适用：

- 未完成 QR 交易，例如用户扫码后放弃、CPM 等待输密。
- Visa/Mastercard/Apple Pay 授权交易实时 void。

官方文档列出的 reversal pay_type：

- QR 未完成：支付宝 MPM `800101`、支付宝 MPM 香港 `801501`、微信 MPM `800201`、支付宝 CPM `800108`。
- 卡/Apple 授权 void：Visa/Mastercard `802801`、Apple Pay `806527`。

不要用 reversal 退已成功的 QR 支付。成功交易退款用 `/trade/v1/refund`。

参数：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `mchid` | 条件必填 | 代理或特定配置要求时传。 |
| `syssn` | 是* | 要冲正的 QFPay 交易号。 |
| `out_trade_no` | 是* | 要冲正的商户订单号。 |
| `txamt` | 是 | 原交易金额，单位分。 |
| `txdtm` | 是 | 原交易时间，`YYYY-MM-DD HH:mm:ss`。 |
| `udid` | 否 | 设备标识。 |

`syssn` 和 `out_trade_no` 至少传一个。

处理：

- `0000`：冲正/撤销成功。
- `1143` 或 `1145`：处理中，轮询 `/trade/v1/query`。
- 其他：失败或不可操作。先查原订单再决定下一步。

### Close

Endpoint：`GET /trade/v1/close`。

用于 QFPay 文档要求 close 而非 reversal 的钱包/模式，尤其部分微信 CPM：

- `800008` 泛 CPM for WeChat。
- `800208` WeChat CPM。
- `801008` WeChat Pay HK CPM 直清。

参数风格和 reversal 类似：条件 `mchid`、`syssn` 或 `out_trade_no`、`txamt`、`txdtm`、可选 `udid`。

## 预授权

适用于最终扣款金额未知的场景，例如酒店、租赁、延迟发货、变量定价。

创建预授权交易通过 Payment Element SDK 完成，初始阶段只冻结资金，不扣款。

扣款 capture：

- Endpoint：`POST /trade/v1/authtrade`。
- 必填：`txamt`、原预授权订单 `syssn`。
- 可选/条件：`txcurrcd`、`mchid`。
- 可多次部分扣款，但总额不能超过授权金额。

解冻 unfreeze：

- Endpoint：`POST /trade/v1/unfreeze`。
- 必填：`txamt`、`txdtm`、原预授权 `syssn`、原 `out_trade_no`。
- 可选/条件：`mchid`。
- 解冻只能做一次；解冻后不能再扣款。

已扣款后的退款：

- 用 `/trade/v1/refund`。
- 传 capture 步骤返回的 `syssn`，不要传原预授权 `syssn`。

QFPay 文档列出的 capture 窗口：

- 一般商户：最多 7 天。
- 酒店/租赁：最多 28 天。
- 实际窗口取决于商户协议和通道能力。

## 异步通知

QFPay 可以把成功支付/退款结果 POST 到商户回调地址。

规则：

- 回调 URL 需要发给 QFPay 技术支持配置。
- 方法：`POST`。
- `Content-Type: application/json`。
- 只允许端口 80 和 443。
- 一个 `app_code` + `client_key` 只能绑定一个通知 URL。代理场景应使用统一入口区分子商户。
- 未收到 HTTP `200` 且 body 为 `SUCCESS` 时会重试，间隔大约为 2 分钟、10 分钟、10 分钟、60 分钟、2 小时、6 小时、15 小时。
- 官方列出的回调 IP：`13.228.112.115`、`18.138.115.47`、`18.166.202.92`。

验签：

```python
import hashlib

def verify_qfpay_callback(raw_body: bytes, client_key: str, signature: str) -> bool:
    expected = hashlib.md5(raw_body + client_key.encode("utf-8")).hexdigest().upper()
    return expected == signature.upper()
```

常见字段：

| 字段 | 说明 |
| --- | --- |
| `status` | `1` 表示支付成功。 |
| `notify_type` | `payment`、`refund`，预授权场景可能有 `unfreeze`。 |
| `pay_type` | 支付方式代码。 |
| `syssn` | QFPay 交易号。 |
| `out_trade_no` | 商户订单号。 |
| `txamt` | 金额，单位分。 |
| `txcurrcd` | 币种。 |
| `txdtm` | 商户侧交易时间。 |
| `sysdtm` | QFPay 系统时间，也是结算 cutoff 参考。 |
| `paydtm` | 支付完成时间。 |
| `cancel` | 撤销/退款标记。 |
| `respcd` | 成功通知通常为 `0000`。 |

`cancel` 值：

| 值 | 含义 |
| --- | --- |
| `0` | 未撤销。 |
| `1` | CPM 已冲正或已退款。 |
| `2` | MPM 已取消。 |
| `3` | 已退款。 |
| `4` | 支付宝预授权订单完成。 |
| `5` | 部分退款。 |

回调处理必须按 `syssn` 和 `out_trade_no` 幂等。验签失败、回调延迟、本地状态冲突时，不要直接相信回调，改用查询接口确认。

## 状态码和重试策略

核心处理表：

| 代码 | 含义 | 动作 |
| --- | --- | --- |
| `0000` | 成功 | 保存交易号。用户交互支付仍通过回调/查询确认最终结果。 |
| `1143` | 未支付或用户输密中 | 不新建订单，延迟查询。 |
| `1145` | 处理中 | 不新建订单，延迟查询。 |
| `1298` | 网络延迟，可能已支付 | 不立即重试支付，先查询。 |
| `1108` | 签名错误 | 重新检查签名串、算法、环境和凭证。 |
| `2011` | 交易流水重复 | 按 `out_trade_no` 查询，不要直接换号。 |
| `1125`、`1262` | 已退款 | 查退款/原单并对账。 |
| `1260` | 已支付 | 查单并对账。 |
| `1261` | 未支付 | 退款/撤销当前不成立，查原单。 |
| `1263`、`1264` | 已取消/已关闭 | 查单并对账。 |
| `1266`、`1267` | 金额或订单信息不匹配 | 停止操作，核对本地订单数据。 |
| `1268` | 订单不存在 | 核对订单号、商户号、时间窗口。 |
| `1270`、`1271` | 不支持部分退款 | 只有业务确认后才考虑全额退款。 |
| `1272` | 退款金额超过可退金额 | 查询可退金额，修正请求。 |
| `1294` | 银行/风控禁止 | 不自动重试，交给运营或用户处理。 |
| `1295`、`1296` | 网络拥堵 | 只在幂等安全时退避重试。 |
| HTTP `429` | 触发限流 | 退避。官方文档为每商户 100 RPS 和 400 requests/min。 |

重试原则：

1. 资金动作重试前先查状态。
2. 同一业务意图使用同一个 `out_trade_no`。
3. 不要通过更换 `out_trade_no` 来绕过 pending。
4. 429、网络拥堵使用指数退避。
5. 日志保留完整响应，但脱敏密钥、签名、身份信息和卡信息。

## Android App-to-App POS SDK

当第三方 Android POS App 需要本地调起 QFPay HaoJin App，而不是直接调用 OpenAPI 时使用。

配置：

- 设备必须安装 HaoJin App。
- AndroidManifest 加权限：`com.qfpay.haojin.permission.OPEN_API`。
- 引入 SDK JAR。官方页面当前写的是 `2.3.4.jar`。
- 设置目标 App ID：`Config.setTargetAppId("in.haojin.nearbymerchant.oversea")`。
- 创建 API 实例：`TradeApiFactory.createTradeApi(activity, callback)`。

常用操作：

| 操作 | SDK 入口 |
| --- | --- |
| 收款/支付 | `new CollectionReq(amount)` 后 `mTradeApi.doTrade(req)` |
| 扫用户付款码 | `req.setScan_type(CollectionReq.SCAN_TYPE_SCAN)` |
| 展示二维码 | `req.setScan_type(CollectionReq.SCAN_TYPE_QRCODE)` |
| 退款 | `new RefundReq(qfOrderId)` |
| 交易列表 | `new GetTransListReq()` 并设置 channel/type/month/time/page |
| 交易详情 | `new GetTransReq(qfOrderId)`，可选 `setOut_trade_no(...)` |
| 交易汇总 | `new CheckTradeSumReq()` |
| 用户配置 | `new GetUserConfigReq()` |
| 预授权扣款 | `new PreAuthTransDeductReq(transId)` |
| 预授权取消 | `new PreAuthTransCancelReq(transId)` |
| 预授权列表 | `new PreAuthTransListReq(pageSize, pageNum)` |
| 预授权详情 | `new PreAuthTransDetailReq(transId)` |
| 卡退款 | `new CardRefundReq(qfOrderId)` |
| 卡结算 | `new CardSettleReq()` |

解析 SDK 响应时必须判空。QFPay 文档明确 `parseResponse(...)` 可能返回 null。
