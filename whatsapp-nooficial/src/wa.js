/**
 * Baileys connection factory with multi-file auth state persistence.
 */

import { makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } from "@whiskeysockets/baileys";
import { EventEmitter } from "events";

const AUTH_FOLDER = process.env.WA_AUTH_FOLDER || "./wa_auth";

export async function createConnection(logger) {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_FOLDER);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    auth: state,
    printQRInTerminal: false, // we handle QR ourselves
    logger: logger.child({ module: "baileys" }),
    generateHighQualityLinkPreview: false,
  });

  sock.ev.on("creds.update", saveCreds);

  // Wrap sock.ev in a standard EventEmitter for ergonomic usage in index.js
  const events = new EventEmitter();
  sock.ev.on("connection.update", (update) => events.emit("connection.update", update));
  sock.ev.on("messages.upsert", (upsert) => events.emit("messages.upsert", upsert));

  return { sock, events };
}
