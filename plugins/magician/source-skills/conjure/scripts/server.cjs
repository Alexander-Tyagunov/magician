#!/usr/bin/env node
"use strict";

// Magician Visual Companion — local design studio server (HTTP + WebSocket, zero deps).
// Serves versioned mockups, injects helper.js, hot-reloads the browser, and acts as the
// two-way EVENT HUB between the rendered prototype and the Claude session:
//   • inbound  (browser → session): selection/click/chat land in state/events.jsonl (append-only)
//   • pull     (session): GET /magician/<p>/v<n>/events.json?since=<cursor>
//   • outbound (session → browser): append to state/outbox.jsonl → broadcast chat_reply/toast
//   • frames   (session → browser): write .html into screens/v<n>/ → WS reload

const http  = require("http");
const fs    = require("fs");
const path  = require("path");
const crypto = require("crypto");

const DESIGN_DIR   = process.argv[2];
const PROJECT_NAME = process.argv[3] || "project";

if (!DESIGN_DIR) { console.error("Usage: server.cjs <design-dir> <project-name>"); process.exit(1); }

const SCREENS_DIR = path.join(DESIGN_DIR, "screens");
const STATE_DIR   = path.join(DESIGN_DIR, "state");
const SCRIPT_DIR  = __dirname;
const EVENTS_FILE = path.join(STATE_DIR, "events.jsonl");   // append-only inbound log (never wiped)
const OUTBOX_FILE = path.join(STATE_DIR, "outbox.jsonl");   // session → browser messages

for (const d of [SCREENS_DIR, STATE_DIR]) fs.mkdirSync(d, { recursive: true });

const FRAME_TEMPLATE = fs.readFileSync(path.join(SCRIPT_DIR, "frame-template.html"), "utf8");
const HELPER_JS      = fs.readFileSync(path.join(SCRIPT_DIR, "helper.js"), "utf8");

const wsClients = new Map(); // socket → { version }
let lastActivity = Date.now();
const touch = () => { lastActivity = Date.now(); };

// ─── event log helpers ────────────────────────────────────────────────────────

function appendEvent(obj) {
  const rec = { id: crypto.randomUUID(), ts: Date.now(), ...obj };
  try { fs.appendFileSync(EVENTS_FILE, JSON.stringify(rec) + "\n"); } catch {}
  return rec;
}

// Return events after line-index `since` (a cursor), plus the new cursor.
function eventsSince(since) {
  let lines = [];
  try {
    lines = fs.readFileSync(EVENTS_FILE, "utf8").split("\n").filter(Boolean);
  } catch {}
  const from = Number.isFinite(since) && since >= 0 ? since : 0;
  const slice = lines.slice(from).map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
  return { cursor: lines.length, events: slice };
}

// ─── Routing helpers ────────────────────────────────────────────────────────

// Parse /magician/<project>/v<n>/<file?> → { version, file }
function parsePath(url) {
  const m = url.match(/^\/magician\/[^/]+\/v(\d+)\/?(.*)$/);
  if (!m) return null;
  return { version: parseInt(m[1], 10), file: m[2] || null };
}

function versionDir(version) { return path.join(SCREENS_DIR, `v${version}`); }

function latestVersion() {
  try {
    const entries = fs.readdirSync(SCREENS_DIR)
      .map(n => parseInt(n.replace("v", ""), 10))
      .filter(n => !isNaN(n))
      .sort((a, b) => b - a);
    return entries[0] || 1;
  } catch { return 1; }
}

function newestFile(dir) {
  try {
    const files = fs.readdirSync(dir)
      .filter(f => f.endsWith(".html"))
      .map(f => ({ name: f, mtime: fs.statSync(path.join(dir, f)).mtimeMs }))
      .sort((a, b) => b.mtime - a.mtime);
    return files.length ? path.join(dir, files[0].name) : null;
  } catch { return null; }
}

// ─── Screen serving ─────────────────────────────────────────────────────────

function serve404(res, msg) {
  res.writeHead(404, { "Content-Type": "text/html" });
  res.end(`<html><body style="font:14px monospace;padding:2rem;background:#0a0a0f;color:#64748b">${msg}</body></html>`);
}

// Companion chat is opt-in: the /conjure skill writes state/companion.json {"chat":true}
// only after the user agrees. Off by default → no chat bubble is rendered.
function companionChatEnabled() {
  try { return !!JSON.parse(fs.readFileSync(path.join(STATE_DIR, "companion.json"), "utf8")).chat; } catch { return false; }
}

function injectHelper(html, version, port) {
  return html.replace(
    "</body>",
    `<script>window.__VC_PORT=${port};window.__VC_VERSION="${version}";window.__VC_PROJECT=${JSON.stringify(PROJECT_NAME)};window.__VC_CHAT=${companionChatEnabled()};\n${HELPER_JS}\n</script>\n</body>`
  );
}

function serveScreen(res, filepath, version, port) {
  let html = fs.readFileSync(filepath, "utf8");
  const isFullDoc = /^<!DOCTYPE/i.test(html.trim()) || /^<html/i.test(html.trim());
  if (!isFullDoc) {
    html = FRAME_TEMPLATE
      .replace(/\{\{PROJECT\}\}/g, PROJECT_NAME)
      .replace(/\{\{VERSION\}\}/g, `v${version}`)
      .replace("<!-- CONTENT -->", html);
  }
  html = injectHelper(html, version, port);
  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
  res.end(html);
}

// ─── HTTP server ─────────────────────────────────────────────────────────────

let port;

const server = http.createServer((req, res) => {
  touch();
  const url = req.url.split("?")[0];
  const query = Object.fromEntries(new URLSearchParams(req.url.split("?")[1] || ""));

  // Redirect /magician/<project>/latest/ → /magician/<project>/v<n>/
  if (url.match(/^\/magician\/[^/]+\/latest\/?$/)) {
    res.writeHead(302, { Location: `/magician/${PROJECT_NAME}/v${latestVersion()}/` }); res.end(); return;
  }
  if (url === "/" || url === "") {
    res.writeHead(302, { Location: `/magician/${PROJECT_NAME}/v${latestVersion()}/` }); res.end(); return;
  }

  // ── inbound event hub API ──
  // POST /magician/<p>/v<n>/chat   { text }           → append chat event, ack the browser
  // POST /magician/<p>/v<n>/event  { type, ...}       → append arbitrary UI event
  // GET  /magician/<p>/v<n>/events.json?since=<cursor> → { cursor, events } (session pull)
  const apiMatch = url.match(/^\/magician\/[^/]+\/v(\d+)\/(chat|event|events\.json)$/);
  if (apiMatch) {
    const version = parseInt(apiMatch[1], 10);
    const kind = apiMatch[2];
    if (kind === "events.json" && req.method === "GET") {
      const { cursor, events } = eventsSince(parseInt(query.since, 10));
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ cursor, events }));
      return;
    }
    if ((kind === "chat" || kind === "event") && req.method === "POST") {
      let body = "";
      req.on("data", c => { body += c; if (body.length > 64 * 1024) req.destroy(); });
      req.on("end", () => {
        let obj = {};
        try { obj = JSON.parse(body || "{}"); } catch {}
        const text = typeof obj.text === "string" ? obj.text.slice(0, 4000) : "";
        const rec = kind === "chat"
          ? appendEvent({ type: "chat", version, text })
          : appendEvent({ ...obj, type: String(obj.type || "event"), version });
        if (kind === "chat") broadcast({ type: "chat_ack", id: rec.id, ts: rec.ts }, version);
        res.writeHead(202, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true, id: rec.id }));
      });
      return;
    }
  }

  const parsed = parsePath(url);
  if (!parsed) { serve404(res, `Unknown path: ${url}`); return; }

  const { version, file } = parsed;
  const vDir = versionDir(version);
  fs.mkdirSync(vDir, { recursive: true });

  if (file) {
    const filepath = path.join(vDir, file);
    if (!fs.existsSync(filepath)) { serve404(res, `Screen not found: ${file}`); return; }
    serveScreen(res, filepath, version, port);
  } else {
    const filepath = newestFile(vDir);
    if (!filepath) {
      const waiting = FRAME_TEMPLATE
        .replace(/\{\{PROJECT\}\}/g, PROJECT_NAME)
        .replace(/\{\{VERSION\}\}/g, `v${version}`)
        .replace("<!-- CONTENT -->", `
          <div style="text-align:center;padding:6rem 2rem;color:var(--muted)">
            <div style="font-size:3rem;margin-bottom:1rem">✦</div>
            <p style="font-size:1.1rem">Waiting for design screens...</p>
          </div>`);
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(injectHelper(waiting, version, port));
      return;
    }
    serveScreen(res, filepath, version, port);
  }
});

// ─── WebSocket ───────────────────────────────────────────────────────────────

server.on("upgrade", (req, socket) => {
  const key = req.headers["sec-websocket-key"];
  if (!key) { socket.destroy(); return; }
  const accept = crypto.createHash("sha1").update(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest("base64");
  socket.write(
    "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n" +
    `Sec-WebSocket-Accept: ${accept}\r\n\r\n`
  );
  const parsed = parsePath(req.url || "/");
  const version = parsed ? parsed.version : latestVersion();
  wsClients.set(socket, { version });

  socket.on("data", buf => {
    touch();
    try {
      const masked = (buf[1] & 0x80) !== 0;
      let payLen = buf[1] & 0x7f;
      let offset = 2;
      if (payLen === 126) { payLen = buf.readUInt16BE(2); offset = 4; }
      else if (payLen === 127) { payLen = Number(buf.readBigUInt64BE(2)); offset = 10; }
      const mask = masked ? buf.slice(offset, offset + 4) : null;
      offset += masked ? 4 : 0;
      const payload = Buffer.from(buf.slice(offset, offset + payLen));
      if (masked && mask) for (let i = 0; i < payload.length; i++) payload[i] ^= mask[i % 4];
      const msg = JSON.parse(payload.toString("utf8"));
      if (msg.type === "click" || msg.type === "select" || msg.type === "selection") {
        appendEvent({ type: msg.type, version, choice: msg.choice, text: msg.text, target: msg.target });
      } else if (msg.type === "chat") {
        const rec = appendEvent({ type: "chat", version, text: String(msg.text || "").slice(0, 4000) });
        broadcast({ type: "chat_ack", id: rec.id, ts: rec.ts }, version);
      }
    } catch {}
  });
  socket.on("close", () => wsClients.delete(socket));
  socket.on("error", () => wsClients.delete(socket));
});

function wsFrame(data) {
  const payload = Buffer.from(data, "utf8");
  let frame;
  if (payload.length < 126) {
    frame = Buffer.allocUnsafe(2 + payload.length);
    frame[0] = 0x81; frame[1] = payload.length; payload.copy(frame, 2);
  } else if (payload.length < 65536) {
    frame = Buffer.allocUnsafe(4 + payload.length);
    frame[0] = 0x81; frame[1] = 126; frame.writeUInt16BE(payload.length, 2); payload.copy(frame, 4);
  } else {
    frame = Buffer.allocUnsafe(10 + payload.length);
    frame[0] = 0x81; frame[1] = 127; frame.writeBigUInt64BE(BigInt(payload.length), 2); payload.copy(frame, 10);
  }
  return frame;
}

function broadcast(msg, targetVersion) {
  const data = wsFrame(JSON.stringify(msg));
  for (const [socket, meta] of wsClients) {
    if (targetVersion === undefined || meta.version === targetVersion) {
      try { socket.write(data); } catch { wsClients.delete(socket); }
    }
  }
}

// ─── File watching: frames (reload / new_version) + outbox (session → browser) ──

let reloadTimer;
fs.watch(SCREENS_DIR, { recursive: true }, (event, filename) => {
  if (!filename || !filename.endsWith(".html")) return;
  touch();
  clearTimeout(reloadTimer);
  reloadTimer = setTimeout(() => {
    const m = String(filename).match(/^v(\d+)[\\/]/);
    const version = m ? parseInt(m[1], 10) : undefined;
    const latest = latestVersion();
    // Reload viewers on this version; NOTE: events.jsonl is intentionally NOT wiped so
    // selections/chat made before a push survive (the session consumes via a cursor).
    broadcast({ type: "reload", version }, version);
    // Nudge viewers stuck on an older version with a clickable upgrade banner.
    if (version === latest) {
      const url = `http://localhost:${port}/magician/${PROJECT_NAME}/v${latest}/`;
      for (const [, meta] of wsClients) if (meta.version < latest) { broadcast({ type: "new_version", url, version: latest }); break; }
    }
  }, 100);
});

// Session → browser messages (chat replies, toasts). Session appends JSON lines to outbox.jsonl.
let outboxCursor = 0;
try { outboxCursor = fs.readFileSync(OUTBOX_FILE, "utf8").split("\n").filter(Boolean).length; } catch {}
function drainOutbox() {
  let lines = [];
  try { lines = fs.readFileSync(OUTBOX_FILE, "utf8").split("\n").filter(Boolean); } catch { return; }
  for (const l of lines.slice(outboxCursor)) {
    try { const m = JSON.parse(l); broadcast({ type: m.type || "chat_reply", ...m }, m.version); } catch {}
  }
  outboxCursor = lines.length;
}
try {
  fs.watch(STATE_DIR, (event, filename) => { if (filename === "outbox.jsonl") { touch(); drainOutbox(); } });
} catch {}

// ─── Start ───────────────────────────────────────────────────────────────────

function start(candidatePort) {
  server.once("error", err => {
    if (err.code === "EADDRINUSE") start(Math.floor(Math.random() * 16383) + 49152);
    else { console.error(err); process.exit(1); }
  });
  server.listen(candidatePort, "127.0.0.1", () => {
    port = server.address().port;
    const urlBase = `http://localhost:${port}/magician/${PROJECT_NAME}`;
    const info = {
      port, project: PROJECT_NAME, url_base: urlBase, latest_url: `${urlBase}/latest/`,
      design_dir: DESIGN_DIR, screens_dir: SCREENS_DIR, state_dir: STATE_DIR,
      events_file: EVENTS_FILE, outbox_file: OUTBOX_FILE,
    };
    fs.writeFileSync(path.join(STATE_DIR, "server-info"), JSON.stringify(info, null, 2));
    console.log(`✦ Magician Design Companion → ${urlBase}/v1/`);
  });
}

start(Math.floor(Math.random() * 16383) + 49152);

// Auto-exit only when truly idle AND no browser is connected — so a long live design
// session (with a viewer open, or a monitor/loop attached) is never killed mid-flow.
setInterval(() => {
  if (wsClients.size === 0 && Date.now() - lastActivity > 90 * 60 * 1000) process.exit(0);
}, 60_000);

process.on("SIGTERM", () => process.exit(0));
process.on("SIGINT",  () => process.exit(0));
