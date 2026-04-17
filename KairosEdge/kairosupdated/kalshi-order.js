// netlify/functions/kalshi-order.js
// Proxies authenticated order requests to Kalshi trading API
// Uses RSA-PSS signing — private key stored in Netlify env, never in browser

const crypto = require("crypto");

// P1-8: All Kalshi API calls use this single official base URL
const BASE_URL = "https://api.elections.kalshi.com";
// P1-9: No hardcoded fallback — key must be in Netlify env vars
const API_KEY_ID = process.env.KALSHI_API_KEY_ID;
// P0-7: Origin allowlist — set KALSHI_ALLOWED_ORIGIN env var to your Netlify URL
// e.g. "https://yoursite.netlify.app" (comma-separate multiple origins)
const ALLOWED_ORIGINS = (process.env.KALSHI_ALLOWED_ORIGIN || "").split(",").map(s => s.trim()).filter(Boolean);

function getPrivateKey() {
  const raw = process.env.KALSHI_PRIVATE_KEY;
  if (!raw) throw new Error("KALSHI_PRIVATE_KEY env var not set");
  // Netlify sometimes collapses newlines — restore PEM format
  let pem = raw;
  if (!pem.includes("\n")) {
    pem = pem
      .replace("-----BEGIN RSA PRIVATE KEY-----", "-----BEGIN RSA PRIVATE KEY-----\n")
      .replace("-----END RSA PRIVATE KEY-----", "\n-----END RSA PRIVATE KEY-----")
      .replace(/(.{64})/g, "$1\n");
  }
  return pem;
}

function signRequest(method, path, timestampMs) {
  const pem = getPrivateKey();
  const msg = `${timestampMs}${method.toUpperCase()}${path}`;
  const sig = crypto.sign("sha256", Buffer.from(msg), {
    key: pem,
    padding: crypto.constants.RSA_PKCS1_PSS_PADDING,
    saltLength: crypto.constants.RSA_PSS_SALTLEN_DIGEST,
  });
  return sig.toString("base64");
}

async function kalshiRequest(method, path, body = null) {
  const timestampMs = Date.now().toString();
  const pathForSig = path.split("?")[0]; // strip query params before signing
  const sig = signRequest(method, pathForSig, timestampMs);

  const headers = {
    "Content-Type": "application/json",
    "KALSHI-ACCESS-KEY": API_KEY_ID,
    "KALSHI-ACCESS-SIGNATURE": sig,
    "KALSHI-ACCESS-TIMESTAMP": timestampMs,
  };

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(BASE_URL + path, opts);
  const text = await res.text();
  let json;
  try { json = JSON.parse(text); } catch { json = { raw: text }; }
  return { status: res.status, ok: res.ok, data: json };
}

exports.handler = async (event) => {
  // P0-7: Strict origin check — reject requests not from your own app
  const origin = event.headers.origin || event.headers.Origin || "";
  const originOk = ALLOWED_ORIGINS.length === 0 || ALLOWED_ORIGINS.includes(origin);
  const cors = {
    "Access-Control-Allow-Origin": originOk ? (origin || "*") : "null",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Vary": "Origin",
  };

  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 200, headers: cors, body: "" };
  }

  if (!originOk) {
    return { statusCode: 403, headers: cors, body: JSON.stringify({ error: "Forbidden: origin not allowed" }) };
  }

  if (event.httpMethod !== "POST") {
    return { statusCode: 405, headers: cors, body: JSON.stringify({ error: "Method not allowed" }) };
  }

  // P1-9: Fail loudly if key missing rather than using hardcoded fallback
  if (!API_KEY_ID) {
    return { statusCode: 500, headers: cors, body: JSON.stringify({ error: "KALSHI_API_KEY_ID env var not set in Netlify" }) };
  }

  let body;
  try {
    body = JSON.parse(event.body || "{}");
  } catch {
    return { statusCode: 400, headers: cors, body: JSON.stringify({ error: "Invalid JSON" }) };
  }

  const { action, ticker, side, count, yes_price, order_id } = body;

  try {
    let result;

    // ── WS AUTH TOKEN (for browser WebSocket auth-by-message) ────
    // P0-NEW-2: Browsers can't send custom headers on WS connections. Instead, the browser
    // fetches a fresh RSA-PSS signature from here, then sends it as a cmd:'auth' message.
    // ── WS AUTH TOKEN ────────────────────────────────────────────
    if (action === "get_ws_auth") {
      if (!API_KEY_ID) {
        return { statusCode: 500, headers: cors, body: JSON.stringify({ error: "KALSHI_API_KEY_ID not set" }) };
      }
      const ts = Date.now().toString();
      const sig = signRequest("GET", "/trade-api/ws/v2", ts);
      return {
        statusCode: 200,
        headers: { ...cors, "Content-Type": "application/json" },
        body: JSON.stringify({ apiKeyId: API_KEY_ID, signature: sig, timestamp: ts }),
      };

    // ── TAKE-PROFIT SELL (GTC resting limit — for auto T1 exit) ──────────────
    // place_tp_sell: posts a resting GTC limit sell order at the specified price.
    // Unlike sell_position (IOC), this stays on the book until hit = maker fee rate.
    } else if (action === "place_tp_sell") {
      if (!ticker || !count || yes_price === undefined) {
        return {
          statusCode: 400,
          headers: cors,
          body: JSON.stringify({ error: "Missing required fields: ticker, count, yes_price" }),
        };
      }
      result = await kalshiRequest("POST", "/trade-api/v2/portfolio/orders", {
        ticker,
        action: "sell",          // sell YES contracts
        side: "yes",
        type: "limit",           // resting limit (GTC) — no time_in_force = stays on book
        count: Number(count),
        yes_price: Math.max(1, Math.min(99, Number(yes_price))),
        reduce_only: true,       // never flip to short position
        client_order_id: crypto.randomUUID(),
      });

    // ── GET BALANCE ──────────────────────────────────────────────
    } else if (action === "balance") {
      result = await kalshiRequest("GET", "/trade-api/v2/portfolio/balance");

    // ── PLACE ORDER ──────────────────────────────────────────────
    } else if (action === "place_order") {
      if (!ticker || !side || !count || !yes_price) {
        return {
          statusCode: 400,
          headers: cors,
          body: JSON.stringify({ error: "Missing required fields: ticker, side, count, yes_price" }),
        };
      }

      const orderData = {
        ticker,
        action: "buy",
        side: side || "yes",        // "yes" = trailing team wins
        type: "limit",
        count: Number(count),
        yes_price: Number(yes_price), // cents 1-99
        client_order_id: crypto.randomUUID(), // P3-19: UUID v4, no timestamp collision risk
      };

      result = await kalshiRequest("POST", "/trade-api/v2/portfolio/orders", orderData);

    // ── SELL POSITION (for filled orders) ────────────────────────
    // P0-1: cancelPosOrder() calls this for filled contracts. cancel_order only works on resting (unfilled) orders.
    } else if (action === "sell_position") {
      if (!ticker || !count || yes_price === undefined) {
        return {
          statusCode: 400,
          headers: cors,
          body: JSON.stringify({ error: "Missing required fields: ticker, count, yes_price" }),
        };
      }
      result = await kalshiRequest("POST", "/trade-api/v2/portfolio/orders", {
        ticker,
        action: "sell",
        side: "yes",
        type: "limit",
        count: Number(count),
        yes_price: Math.max(1, Number(yes_price)), // 1¢ floor — Kalshi minimum
        reduce_only: true,                          // never flip to short
        time_in_force: "immediate_or_cancel",       // simulate market order
        client_order_id: crypto.randomUUID(),
      });

    // ── GET ORDER STATUS ─────────────────────────────────────────
    } else if (action === "get_order") {
      if (!order_id) {
        return { statusCode: 400, headers: cors, body: JSON.stringify({ error: "Missing order_id" }) };
      }
      result = await kalshiRequest("GET", `/trade-api/v2/portfolio/orders/${order_id}`);

    // ── CANCEL ORDER ─────────────────────────────────────────────
    } else if (action === "cancel_order") {
      if (!order_id) {
        return { statusCode: 400, headers: cors, body: JSON.stringify({ error: "Missing order_id" }) };
      }
      result = await kalshiRequest("DELETE", `/trade-api/v2/portfolio/orders/${order_id}`);

    // ── GET POSITIONS ─────────────────────────────────────────────
    } else if (action === "get_positions") {
      // P1-7: settlement_status=unsettled was removed from Kalshi positions API. count_filter=position is sufficient.
      result = await kalshiRequest("GET", "/trade-api/v2/portfolio/positions?limit=50&count_filter=position");

    // ── GET ORDERBOOK (liquidity check before entry) ──────────────
    // Returns bids/asks for depth analysis — used to verify ≥500 contracts within 3¢ of entry
    } else if (action === "get_orderbook") {
      if (!ticker) {
        return { statusCode: 400, headers: cors, body: JSON.stringify({ error: "Missing ticker" }) };
      }
      result = await kalshiRequest("GET", `/trade-api/v2/markets/${encodeURIComponent(ticker)}/orderbook`);

    } else {
      return { statusCode: 400, headers: cors, body: JSON.stringify({ error: `Unknown action: ${action}` }) };
    }

    return {
      statusCode: result.status,
      headers: { ...cors, "Content-Type": "application/json" },
      body: JSON.stringify(result.data),
    };

  } catch (err) {
    console.error("Kalshi order error:", err);
    return {
      statusCode: 500,
      headers: cors,
      body: JSON.stringify({ error: err.message }),
    };
  }
};
