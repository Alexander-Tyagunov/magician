#!/usr/bin/env node
"use strict";

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

for (const d of [SCREENS_DIR, STATE_DIR]) fs.mkdirSync(d, { recursive: true });

const FRAME_TEMPLATE = fs.readFileSync(path.join(SCRIPT_DIR, "frame-template.html"), "utf8");
const HELPER_JS      = fs.readFileSync(path.join(SCRIPT_DIR, "helper.js"), "utf8");

const wsClients = new Map(); // socket → { version }

// ─── Routing helpers ────────────────────────────────────────────────────────

// Parse /magician/<project>/v<n>/<file?> → { version, file }
function parsePath(url) {
  const m = url.match(/^\/magician\/[^/]+\/v(\d+)\/?(.*)$/);
  if (!m) return null;
  return { version: parseInt(m[1], 10), file: m[2] || null };
}

function versionDir(version) {
  return path.join(SCREENS_DIR, `v${version}`);
}

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

function serveScreen(res, filepath, version, port) {
  let html = fs.readFileSync(filepath, "utf8");
  const isFullDoc = /^<!DOCTYPE/i.test(html.trim()) || /^<html/i.test(html.trim());

  if (!isFullDoc) {
    html = FRAME_TEMPLATE
      .replace(/\{\{PROJECT\}\}/g, PROJECT_NAME)
      .replace(/\{\{VERSION\}\}/g, `v${version}`)
      .replace("<!-- CONTENT -->", html);
  }

  // Inject helper + port info before </body>
  html = html.replace(
    "</body>",
    `<script>window.__VC_PORT=${port};window.__VC_VERSION="${version}";\n${HELPER_JS}\n</script>\n</body>`
  );

  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
  res.end(html);
}

// ─── HTTP server ─────────────────────────────────────────────────────────────

let port;

const server = http.createServer((req, res) => {
  const url = req.url.split("?")[0];

  // Redirect /magician/<project>/latest/ → /magician/<project>/v<n>/
  if (url.match(/^\/magician\/[^/]+\/latest\/?$/)) {
    const v = latestVersion();
    res.writeHead(302, { Location: `/magician/${PROJECT_NAME}/v${v}/` });
    res.end();
    return;
  }

  // Waiting room at root
  if (url === "/" || url === "") {
    const v = latestVersion();
    res.writeHead(302, { Location: `/magician/${PROJECT_NAME}/v${v}/` });
    res.end();
    return;
  }

  const parsed = parsePath(url);
  if (!parsed) { serve404(res, `Unknown path: ${url}`); return; }

  const { version, file } = parsed;
  const vDir = versionDir(version);
  fs.mkdirSync(vDir, { recursive: true });

  if (file) {
    // Specific file
    const filepath = path.join(vDir, file);
    if (!fs.existsSync(filepath)) { serve404(res, `Screen not found: ${file}`); return; }
    serveScreen(res, filepath, version, port);
  } else {
    // Newest file in this version dir
    const filepath = newestFile(vDir);
    if (!filepath) {
      const waiting = FRAME_TEMPLATE
        .replace(/\{\{PROJECT\}\}/g, PROJECT_NAME)
        .replace(/\{\{VERSION\}\}/g, `v${version}`)
        .replace("<!-- CONTENT -->", `
          <div style="text-align:center;padding:6rem 2rem;color:var(--muted)">
            <div style="font-size:3rem;margin-bottom:1rem">✦</div>
            <p style="font-size:1.1rem">Waiting for design screens...</p>
          </div>
        `);
      const withHelper = waiting.replace("</body>", `<script>window.__VC_PORT=${port};window.__VC_VERSION="${version}";\n${HELPER_JS}\n</script>\n</body>`);
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(withHelper);
      return;
    }
    serveScreen(res, filepath, version, port);
  }
});

// ─── WebSocket ───────────────────────────────────────────────────────────────

server.on("upgrade", (req, socket) => {
  const key = req.headers["sec-websocket-key"];
  if (!key) { socket.destroy(); return; }

  const accept = crypto
    .createHash("sha1")
    .update(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11")
    .digest("base64");

  socket.write(
    "HTTP/1.1 101 Switching Protocols\r\n" +
    "Upgrade: websocket\r\nConnection: Upgrade\r\n" +
    `Sec-WebSocket-Accept: ${accept}\r\n\r\n`
  );

  const url = req.url || "/";
  const parsed = parsePath(url);
  const version = parsed ? parsed.version : latestVersion();
  wsClients.set(socket, { version });

  socket.on("data", buf => {
    try {
      const masked = (buf[1] & 0x80) !== 0;
      let payLen = buf[1] & 0x7f;
      let offset = 2;
      if (payLen === 126) { payLen = (buf[2] << 8) | buf[3]; offset = 4; }
      else if (payLen === 127) { payLen = buf.readUInt32BE(6); offset = 10; }

      const mask = masked ? buf.slice(offset, offset + 4) : null;
      offset += masked ? 4 : 0;

      const payload = Buffer.from(buf.slice(offset, offset + payLen));
      if (masked && mask) for (let i = 0; i < payload.length; i++) payload[i] ^= mask[i % 4];

      const msg = JSON.parse(payload.toString("utf8"));
      if (msg.type === "click" || msg.type === "select") {
        fs.appendFileSync(path.join(STATE_DIR, "events"), JSON.stringify({ ...msg, ts: Date.now() }) + "\n");
      }
    } catch {}
  });

  socket.on("close", () => wsClients.delete(socket));
  socket.on("error", () => wsClients.delete(socket));
});

function wsFrame(data) {
  const payload = Buffer.from(data, "utf8");
  const frame = Buffer.allocUnsafe(payload.length < 126 ? 2 + payload.length : 4 + payload.length);
  frame[0] = 0x81;
  if (payload.length < 126) {
    frame[1] = payload.length;
    payload.copy(frame, 2);
  } else {
    frame[1] = 126;
    frame.writeUInt16BE(payload.length, 2);
    payload.copy(frame, 4);
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

// ─── File watching ───────────────────────────────────────────────────────────

let reloadTimer;
fs.watch(SCREENS_DIR, { recursive: true }, (event, filename) => {
  if (!filename?.endsWith(".html")) return;
  clearTimeout(reloadTimer);
  reloadTimer = setTimeout(() => {
    // Clear events on new screen push
    try { fs.writeFileSync(path.join(STATE_DIR, "events"), ""); } catch {}

    // Determine which version this file belongs to
    const m = filename.match(/^v(\d+)\//);
    const version = m ? parseInt(m[1], 10) : undefined;
    broadcast({ type: "reload", version }, version);
  }, 100);
});

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
      port,
      project: PROJECT_NAME,
      url_base: urlBase,
      latest_url: `${urlBase}/latest/`,
      design_dir: DESIGN_DIR,
      screens_dir: SCREENS_DIR,
      state_dir: STATE_DIR,
    };
    fs.writeFileSync(path.join(STATE_DIR, "server-info"), JSON.stringify(info, null, 2));
    console.log(`✦ Magician Design Companion → ${urlBase}/v1/`);
  });
}

start(Math.floor(Math.random() * 16383) + 49152);

// Auto-exit after 90 min inactivity
let lastActivity = Date.now();
setInterval(() => {
  if (Date.now() - lastActivity > 90 * 60 * 1000) process.exit(0);
}, 60_000);

process.on("SIGTERM", () => process.exit(0));
process.on("SIGINT",  () => process.exit(0));
