import crypto from "node:crypto";
import http from "node:http";

const required = ["QFPAY_APP_CODE", "QFPAY_CLIENT_KEY"];
for (const name of required) {
  if (!process.env[name]) throw new Error(`Missing server-side environment variable ${name}`);
}
if ((process.env.QFPAY_ENV || "qa") !== "qa") {
  throw new Error("This template is Sandbox-first. Complete a Go-live review before enabling another environment.");
}

const baseUrl = process.env.QFPAY_BASE_URL || "https://openapi-int.qfapi.com";
const appCode = process.env.QFPAY_APP_CODE;
const clientKey = process.env.QFPAY_CLIENT_KEY;
const processedEvents = new Set(); // Replace with a durable database table keyed by syssn + out_trade_no.

function qfpaySignature(params, algorithm = "sha256") {
  const canonical = Object.entries(params)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .sort(([left], [right]) => left.localeCompare(right, "en"))
    .map(([key, value]) => `${key}=${value}`)
    .join("&");
  return crypto.createHash(algorithm).update(canonical + clientKey, "utf8").digest("hex").toUpperCase();
}

function callbackSignature(rawBody) {
  return crypto.createHash("md5").update(rawBody).update(clientKey, "utf8").digest("hex").toUpperCase();
}

async function readJson(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  const rawBody = Buffer.concat(chunks);
  return { rawBody, data: JSON.parse(rawBody.toString("utf8")) };
}

async function transactionEnquiry({ syssn, out_trade_no }) {
  const params = syssn ? { syssn } : { out_trade_no };
  const response = await fetch(`${baseUrl}/trade/v1/query`, {
    method: "POST",
    headers: {
      "content-type": "application/x-www-form-urlencoded",
      "X-QF-APPCODE": appCode,
      "X-QF-SIGN": qfpaySignature(params, "md5")
    },
    body: new URLSearchParams(params)
  });
  return { httpStatus: response.status, payload: await response.json() };
}

function hostedCheckoutUrl({ amount, currency, outTradeNo }) {
  const params = {
    appcode: appCode,
    failed_url: `${process.env.PUBLIC_BASE_URL}/payment/failed`,
    notify_url: `${process.env.PUBLIC_BASE_URL}/qfpay/callback`,
    out_trade_no: outTradeNo,
    paysource: "remotepay_checkout",
    return_url: `${process.env.PUBLIC_BASE_URL}/payment/complete`,
    sign_type: "SHA256",
    txamt: String(amount),
    txcurrcd: currency,
    txdtm: new Date().toISOString().replace("T", " ").slice(0, 19)
  };
  const query = new URLSearchParams({ ...params, sign: qfpaySignature(params, "sha256") });
  return `${baseUrl}/checkstand/#/?${query}`;
}

function isSuccessfulEnquiry(result) {
  const status = String(result.payload.status ?? result.payload.trade_state ?? "").toLowerCase();
  return result.httpStatus >= 200 && result.httpStatus < 300 && result.payload.respcd === "0000" && ["1", "success", "succeeded", "paid"].includes(status);
}

const server = http.createServer(async (request, response) => {
  try {
    if (request.method === "POST" && request.url === "/checkout") {
      const { data } = await readJson(request);
      if (!Number.isSafeInteger(data.amount) || data.amount < 1) throw new Error("amount must be a positive integer in minor units");
      if (!/^[A-Z]{3}$/.test(data.currency || "HKD")) throw new Error("currency must be ISO 4217 uppercase");
      const outTradeNo = `checkout_${crypto.randomUUID()}`;
      // Keep the signed URL out of application JSON, logs, and Agent-visible responses.
      response.writeHead(303, { location: hostedCheckoutUrl({ amount: data.amount, currency: data.currency || "HKD", outTradeNo }), "cache-control": "no-store" });
      response.end();
      return;
    }
    if (request.method === "POST" && request.url === "/qfpay/callback") {
      const { rawBody, data } = await readJson(request);
      const signature = request.headers["x-qf-sign"];
      if (typeof signature !== "string" || !crypto.timingSafeEqual(Buffer.from(callbackSignature(rawBody)), Buffer.from(signature.toUpperCase()))) {
        response.writeHead(400).end("invalid signature");
        return;
      }
      const eventKey = `${data.syssn}:${data.out_trade_no}`;
      if (!processedEvents.has(eventKey)) {
        const enquiry = await transactionEnquiry({ syssn: data.syssn, out_trade_no: data.out_trade_no });
        if (!isSuccessfulEnquiry(enquiry)) {
          // Preserve UNKNOWN/PROCESSING for retry; never acknowledge it as a fulfilled payment.
          response.writeHead(503, { "content-type": "text/plain" }).end("retry later");
          return;
        }
        processedEvents.add(eventKey);
        // Fulfil here only after writing a durable idempotency/state record.
      }
      response.writeHead(200, { "content-type": "text/plain" }).end("SUCCESS");
      return;
    }
    response.writeHead(404).end();
  } catch {
    // Do not log callback bodies, signatures, or client_key.
    response.writeHead(400, { "content-type": "application/json" }).end(JSON.stringify({ error: "invalid request" }));
  }
});

server.listen(3000, () => console.log("QFPay Hosted Checkout Sandbox server listening on :3000"));
