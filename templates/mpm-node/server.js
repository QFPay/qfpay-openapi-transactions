import crypto from "node:crypto";
import http from "node:http";

const { QFPAY_APP_CODE: appCode, QFPAY_CLIENT_KEY: clientKey } = process.env;
if (!appCode || !clientKey) throw new Error("Use server-side Sandbox credentials only.");
if ((process.env.QFPAY_ENV || "qa") !== "qa") throw new Error("This MPM template is Sandbox-only until Go-live approval.");
const baseUrl = process.env.QFPAY_BASE_URL || "https://openapi-int.qfapi.com";

function signature(params) {
  const canonical = Object.entries(params).filter(([, value]) => value !== "" && value != null)
    .sort(([left], [right]) => left.localeCompare(right, "en"))
    .map(([key, value]) => `${key}=${value}`).join("&");
  return crypto.createHash("md5").update(canonical + clientKey, "utf8").digest("hex").toUpperCase();
}

http.createServer(async (request, response) => {
  if (request.method !== "POST" || request.url !== "/payments") return response.writeHead(404).end();
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  try {
    const { amount, payType, outTradeNo } = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    if (!Number.isSafeInteger(amount) || amount < 1 || !/^\d{6}$/.test(payType) || !outTradeNo) throw new Error("invalid payment request");
    const params = { pay_type: payType, txamt: String(amount), txcurrcd: "HKD", out_trade_no: outTradeNo, txdtm: new Date().toISOString().replace("T", " ").slice(0, 19) };
    const api = await fetch(`${baseUrl}/trade/v1/payment`, { method: "POST", headers: { "content-type": "application/x-www-form-urlencoded", "X-QF-APPCODE": appCode, "X-QF-SIGN": signature(params) }, body: new URLSearchParams(params) });
    const result = await api.json();
    // Store syssn, then use Callback + Transaction Enquiry for final state. Do not fulfil from this response alone.
    response.writeHead(api.status, { "content-type": "application/json" }).end(JSON.stringify({ syssn: result.syssn, respcd: result.respcd, qrcode: result.qrcode }));
  } catch {
    response.writeHead(400, { "content-type": "application/json" }).end(JSON.stringify({ error: "invalid request" }));
  }
}).listen(3000, () => console.log("QFPay MPM Sandbox server listening on :3000"));
