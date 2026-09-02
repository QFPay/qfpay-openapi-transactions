---
name: qfpay-openapi-transactions
description: "处理 QFPay OpenAPI 交易集成与操作。Use when Codex needs to create QFPay payment orders for MPM, CPM, Web, WAP/H5, In-App, Hosted Checkout, Element SDK, FPS, cards, Apple Pay; 查询交易状态；发起退款；执行冲正、关闭、撤销、预授权扣款或解冻；处理 QFPay 回调验签；选择 pay_type；生成 QFPay 请求签名。"
---

# QFPay OpenAPI 交易

## 先读这里

优先阅读中文版参考：[references/qfpay-openapi-reference.zh-CN.md](references/qfpay-openapi-reference.zh-CN.md)。它整理了环境、签名、下单、查询、退款、冲正、close、预授权、回调、状态码、`pay_type` 和 POS SDK 入口。

英文参考仍保留在 [references/qfpay-openapi-reference.md](references/qfpay-openapi-reference.md)，用于和英文官方文档术语对照。

执行任何 QFPay 任务时按这个流程走：

1. 确认操作类型：下单、Hosted Checkout、Element Intent、查询、退款、冲正、close、预授权扣款、预授权解冻、回调验签或 POS SDK 调用。
2. 确认环境和凭证：`app_code`、`client_key`、可选 `mchid`。只有 QFPay 发放或通道要求时才传 `mchid`。
3. 涉及生产环境、扣款、退款、撤销、解冻等资金动作时，先确认环境、金额、币种、原订单号和动作意图。
4. 构造参数并删除 `null`、空字符串字段，再生成签名。
5. 发送请求后保存 `out_trade_no` 和 `syssn`。遇到处理中、回调不确定或网络异常时，用 `/trade/v1/query` 查询到最终状态。

环境只能使用这三个 base URL，除非 QFPay 单独发商户专用 endpoint：

| 业务名称 | 官方英文名 | Base URL |
| --- | --- | --- |
| QA | Sandbox | `https://openapi-int.qfapi.com` |
| 线上测试 | Live Testing | `https://test-openapi-hk.qfapi.com` |
| 生产 | Production | `https://openapi-hk.qfapi.com` |

不要使用旧示例或泛化示例里的 `https://api.qfapi.com`。

## 请求规则

标准交易 API 使用 `application/x-www-form-urlencoded`，除非具体页面另有说明。请求头发送 `X-QF-APPCODE` 和 `X-QF-SIGN`；只有使用 SHA256 时才发送 `X-QF-SIGNTYPE: SHA256`。大多数交易示例默认 MD5。

签名规则：把所有请求参数按 ASCII key 升序排序，拼成 `key=value` 并用 `&` 连接，末尾直接追加 `client_key`，用 MD5 或 SHA256 hash，再转大写。不要把空字段、`X-QF-SIGN` 或 `sign` 本身加入签名。不要在前端或移动端暴露 `client_key`。

Hosted Checkout 是 GET URL：`/checkstand/#/?...`。它用 query 参数 `appcode`，不是请求头 `X-QF-APPCODE`；代理/子商户场景用 `mchntid`；先签除 `sign` 外的所有 query 参数，再追加 `sign`。

回调验签和普通 API 不同：用「原始 JSON body + `client_key`」做 MD5，和请求头 `X-QF-SIGN` 比对。只有验签通过且幂等处理成功后才返回 HTTP `200` 和 body `SUCCESS`。

## 操作入口

- 下单：`POST /trade/v1/payment`。适用于 MPM 动态码、CPM 付款码、Web QR、WAP/H5、钱包 In-App、WeChat JSAPI、小程序、FPS App-to-App 等。
- Hosted Checkout：`GET /checkstand/#/?...&sign=...`。跳转到 QFPay 托管收银台。
- Element SDK Intent：`POST /payment_element/v1/create_payment_intent`，前端再用 QFPay Element SDK 完成支付。
- 交易查询：`POST /trade/v1/query`。查支付、退款、冲正、关闭和对账窗口。
- 退款：`POST /trade/v1/refund`。只对成功交易使用，传原支付的 `syssn`。
- 冲正：`POST /trade/v1/reversal`。用于未完成 QR 交易或卡/Apple Pay 授权撤销，不用于成功 QR 交易退款。
- 关闭订单：`GET /trade/v1/close`。用于 QFPay 文档要求 close 而非 reversal 的场景，尤其部分 WeChat CPM。
- 预授权扣款：`POST /trade/v1/authtrade`。从授权资金中扣全额或部分金额。
- 预授权解冻：`POST /trade/v1/unfreeze`。释放未扣款的授权资金。

## 状态处理

`0000` 表示该 API 返回成功或受理成功，但用户侧支付流程仍要通过回调和/或 `/trade/v1/query` 确认最终状态。

`1143`、`1145`、`1298` 视为处理中或网络延迟。不要立刻换新订单号重下单，先按 `syssn` 或 `out_trade_no` 查询。

重复请求、订单状态冲突、已支付、已退款、已关闭等状态码都先查询再对账。`out_trade_no` 必须在同一商户下保持幂等且唯一，支付和退款请求都不能随意复用。

## 签名辅助脚本

用 [scripts/qfpay_sign.py](scripts/qfpay_sign.py) 生成签名、form body 和 cURL。脚本只输出，不会发送请求。

```bash
python3 scripts/qfpay_sign.py \
  --env live-testing \
  --path /trade/v1/query \
  --app-code "$QFPAY_APP_CODE" \
  --client-key "$QFPAY_CLIENT_KEY" \
  --param syssn=20230423000200020088888888 \
  --param mchid=YOUR_MCHID
```

Hosted Checkout URL 示例：

```bash
python3 scripts/qfpay_sign.py \
  --mode checkout \
  --env qa \
  --path /checkstand/#/ \
  --app-code "$QFPAY_APP_CODE" \
  --client-key "$QFPAY_CLIENT_KEY" \
  --sign-type SHA256 \
  --param paysource=remotepay_checkout \
  --param txamt=1000 \
  --param txcurrcd=HKD \
  --param out_trade_no=ORDER_1001 \
  --param txdtm="2026-09-02 12:00:00" \
  --param return_url=https://merchant.example/success \
  --param failed_url=https://merchant.example/failed \
  --param notify_url=https://merchant.example/notify
```

支持环境参数：

```bash
--env qa
--env live-testing
--env production
```

## 安全边界

不要推断退款、冲正、close、capture 或 unfreeze 的订单号和金额。不确定时先查原订单。

不要为了“重试”资金动作而更换 `out_trade_no`。同一意图使用同一个商户订单号，先查状态再决定下一步。

记录请求元数据和完整响应以便审计，但必须脱敏 `client_key`、签名、客户身份字段和卡信息。
