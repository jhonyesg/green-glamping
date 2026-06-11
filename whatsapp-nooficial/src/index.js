/**
 * WhatsApp unofficial bridge — Baileys + Express REST API
 *
 * Endpoints:
 *   GET  /status           — connection status + QR if disconnected
 *   GET  /qr               — QR code as plain text (for terminal scan)
 *   POST /send             — { to, text } → sends WhatsApp message
 *   GET  /messages/:jid    — recent messages for a JID
 *   POST /webhook/register — { url } → register callback for inbound messages
 */

import express from "express";
import pino from "pino";
import qrcode from "qrcode-terminal";
import { createConnection } from "./wa.js";

const logger = pino({ level: process.env.LOG_LEVEL || "info" });
const PORT = parseInt(process.env.PORT || "3001");
const MULTIBOT_CALLBACK_URL = process.env.MULTIBOT_CALLBACK_URL || "";

const app = express();
app.use(express.json());

// ─── State ───────────────────────────────────────────────────────────────────
let waSocket = null;
let qrData = null;
let status = "disconnected";
let registeredWebhooks = MULTIBOT_CALLBACK_URL ? [MULTIBOT_CALLBACK_URL] : [];
const messageBuffer = new Map(); // jid → last 50 messages

// ─── WA connection factory ───────────────────────────────────────────────────
async function startWA() {
  const { sock, events } = await createConnection(logger);
  waSocket = sock;

  events.on("connection.update", ({ qr, connection, lastDisconnect }) => {
    if (qr) {
      qrData = qr;
      status = "qr_pending";
      logger.warn("New QR code generated — scan to connect");
      qrcode.generate(qr, { small: true });
      notifyAdmin(`QR code ready. Scan in Multibot admin at /admin/wa-qr`);
    }
    if (connection === "open") {
      status = "connected";
      qrData = null;
      logger.info("WhatsApp connected");
    }
    if (connection === "close") {
      status = "disconnected";
      logger.warn("WhatsApp disconnected, reconnecting in 5s...");
      notifyAdmin("WhatsApp disconnected. Reconnecting automatically.");
      setTimeout(startWA, 5000);
    }
  });

  events.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;
    for (const msg of messages) {
      if (msg.key.fromMe) continue;
      const jid = msg.key.remoteJid;
      const text =
        msg.message?.conversation ||
        msg.message?.extendedTextMessage?.text ||
        "";
      const entry = {
        id: msg.key.id,
        jid,
        pushName: msg.pushName || "",
        text,
        timestamp: msg.messageTimestamp,
      };
      if (!messageBuffer.has(jid)) messageBuffer.set(jid, []);
      const buf = messageBuffer.get(jid);
      buf.push(entry);
      if (buf.length > 50) buf.shift();

      await forwardToMultibot(entry);
    }
  });
}

async function notifyAdmin(message) {
  // Placeholder — in production, send alert via Telegram to admin chat_id
  logger.warn({ alert: message });
}

async function forwardToMultibot(entry) {
  for (const url of registeredWebhooks) {
    try {
      await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(entry),
      });
    } catch (err) {
      logger.error({ err, url }, "Failed to forward message to Multibot");
    }
  }
}

// ─── REST API ─────────────────────────────────────────────────────────────────
app.get("/status", (req, res) => {
  res.json({ status, qr_available: !!qrData });
});

app.get("/qr", (req, res) => {
  if (!qrData) return res.status(404).json({ error: "No QR available" });
  res.type("text").send(qrData);
});

app.post("/send", async (req, res) => {
  const { to, text } = req.body;
  if (!to || !text) return res.status(400).json({ error: "to and text required" });
  if (!waSocket || status !== "connected") {
    return res.status(503).json({ error: "WhatsApp not connected" });
  }
  try {
    const jid = to.includes("@") ? to : `${to}@s.whatsapp.net`;
    await waSocket.sendMessage(jid, { text });
    res.json({ ok: true });
  } catch (err) {
    logger.error({ err }, "Send failed");
    res.status(500).json({ error: err.message });
  }
});

app.get("/messages/:jid", (req, res) => {
  const jid = req.params.jid.includes("@")
    ? req.params.jid
    : `${req.params.jid}@s.whatsapp.net`;
  res.json(messageBuffer.get(jid) || []);
});

app.post("/webhook/register", (req, res) => {
  const { url } = req.body;
  if (!url) return res.status(400).json({ error: "url required" });
  if (!registeredWebhooks.includes(url)) registeredWebhooks.push(url);
  res.json({ ok: true, webhooks: registeredWebhooks });
});

// ─── Boot ─────────────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  logger.info(`WhatsApp bridge listening on :${PORT}`);
});

startWA().catch((err) => {
  logger.error({ err }, "Failed to start WhatsApp connection");
  process.exit(1);
});
