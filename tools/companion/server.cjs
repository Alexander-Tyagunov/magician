#!/usr/bin/env node
"use strict";

// Magician companion server — one local listener (127.0.0.1, random port, zero deps, Node ≥ 18)
// behind two features:
//
//   design mode (/conjure)   server.cjs <design-dir> <project-name> [state-dir]
//     Serves versioned mockups, injects helper.js, hot-reloads the browser (WebSocket) and acts as
//     the two-way EVENT HUB between the rendered prototype and the Claude session:
//       • inbound  (browser → session): selection/click/chat land in <state>/events.jsonl
//       • pull     (session): GET /magician/<p>/v<n>/events.json?since=<cursor>
//       • outbound (session → browser): append to <state>/outbox.jsonl → broadcast chat_reply/toast
//       • frames   (session → browser): write .html into screens/v<n>/ → WS reload
//     These routes are unchanged from the /conjure-era server (no token in the path).
//
//   plan mode (/blueprint)   server.cjs --plan <plan-dir> <project-name> [state-dir]
//     Serves the plan walkthrough (plan.html with live mode injected) under a per-run token path and
//     relays reviewer events to <state>/events.jsonl; see PROTOCOL.md next to this file for the exact
//     routes. In plan mode the server writes nothing but <state>/events.jsonl (state.json is Claude's)
//     and prints one JSON line with pid/port/token on stdout for vc-start.sh to record.
//
// <state> defaults to <dir>/state; vc-start.sh passes the matching folder under .workspace/local/.
// Both modes listen on 127.0.0.1 only, send no CORS headers and never serve outside their folder.

const http   = require("http");
const fs     = require("fs");
const path   = require("path");
const crypto = require("crypto");

// ─── arguments ───────────────────────────────────────────────────────────────

const argv = process.argv.slice(2);
let PLAN_MODE = false;
let planFlagDir = null;
const positional = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === "--plan") { PLAN_MODE = true; planFlagDir = argv[i + 1] || null; i++; }
  else positional.push(argv[i]);
}
if (!PLAN_MODE && process.env.MAGICIAN_PLAN_DIR) { PLAN_MODE = true; planFlagDir = process.env.MAGICIAN_PLAN_DIR; }

const BASE_DIR     = PLAN_MODE ? planFlagDir : positional[0];
const PROJECT_NAME = (PLAN_MODE ? positional[0] : positional[1]) || "project";
const STATE_ARG    = PLAN_MODE ? positional[1] : positional[2];

if (!BASE_DIR) {
  console.error("Usage: server.cjs <design-dir> <project-name> [state-dir]\n       server.cjs --plan <plan-dir> <project-name> [state-dir]");
  process.exit(1);
}
if (PLAN_MODE && !/^[A-Za-z0-9._-]+$/.test(PROJECT_NAME)) {
  console.error("project-name may hold only letters, digits, . _ - (it is part of the plan URL)");
  process.exit(1);
}

const DESIGN_DIR  = BASE_DIR;
const PLAN_DIR    = PLAN_MODE ? path.resolve(BASE_DIR) : null;
const SCREENS_DIR = path.join(DESIGN_DIR, "screens");
const STATE_DIR   = STATE_ARG || path.join(BASE_DIR, "state");
const SCRIPT_DIR  = __dirname;
const EVENTS_FILE = path.join(STATE_DIR, "events.jsonl");   // append-only inbound log (never wiped)
const OUTBOX_FILE = path.join(STATE_DIR, "outbox.jsonl");   // session → browser messages (design mode)
const STATE_FILE  = path.join(STATE_DIR, "state.json");     // Claude → page (plan mode; read only here)

if (PLAN_MODE) {
  if (!fs.existsSync(path.join(PLAN_DIR, "plan.json"))) { console.error(`no plan.json in ${PLAN_DIR}`); process.exit(1); }
  fs.mkdirSync(STATE_DIR, { recursive: true });
} else {
  for (const d of [SCREENS_DIR, STATE_DIR]) fs.mkdirSync(d, { recursive: true });
}

const FRAME_TEMPLATE = PLAN_MODE ? "" : fs.readFileSync(path.join(SCRIPT_DIR, "frame-template.html"), "utf8");
const HELPER_JS      = PLAN_MODE ? "" : fs.readFileSync(path.join(SCRIPT_DIR, "helper.js"), "utf8");

// Per-run token: part of every plan URL, so a page on another origin can't guess the endpoints.
const TOKEN = crypto.randomBytes(16).toString("hex");

const wsClients  = new Map(); // socket → { version }      (design mode)
const sseClients = new Set(); // res                        (plan mode)
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

// ─── Routing helpers (design mode) ──────────────────────────────────────────

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

// True when `file` resolves (symlinks followed) to a path inside `dir` (symlinks followed).
function insideDir(dir, file) {
  let real, root;
  try { real = fs.realpathSync(file); root = fs.realpathSync(dir); } catch { return false; }
  return real === root || real.startsWith(root + path.sep);
}

// ─── Screen serving (design mode) ───────────────────────────────────────────

function serve404(res, msg) {
  res.writeHead(404, { "Content-Type": "text/html" });
  res.end(`<html><body style="font:14px monospace;padding:2rem;background:#0a0a0f;color:#64748b">${msg}</body></html>`);
}

// Companion chat is opt-in: the /conjure skill writes <state>/companion.json {"chat":true}
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

// ─── Plan mode ───────────────────────────────────────────────────────────────

const MAX_EVENT_BYTES = 8 * 1024;
const MAX_TEXT_CHARS  = 2000;
const EVENT_TYPES = new Set(["step.review", "step.change_request", "step.edit",
                             "plan.change_request", "plan.approved", "plan.rejected"]);
const REVIEW_STATUS   = new Set(["approved", "deferred", "pending"]);
const APPROVED_STATUS = new Set(["approved", "deferred", "edited"]);
const EDIT_FIELDS     = new Set(["intent", "files", "verify", "red.code"]);

function stripControl(s) { return String(s).replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, ""); }

function readPlan() {
  try { return JSON.parse(fs.readFileSync(path.join(PLAN_DIR, "plan.json"), "utf8")); } catch { return null; }
}

function planVersion(plan) { const v = plan && Number(plan.version); return Number.isInteger(v) && v > 0 ? v : 1; }

function stepIds(plan) {
  const out = new Set();
  for (const s of (plan && Array.isArray(plan.steps)) ? plan.steps : []) if (s && typeof s.id === "string") out.add(s.id);
  return out;
}

// Validate a reviewer event; returns { ok: true, event } or { ok: false, error }.
function validateEvent(body, plan) {
  if (!body || typeof body !== "object" || Array.isArray(body)) return { ok: false, error: "body must be a JSON object" };
  const type = body.type;
  if (typeof type !== "string" || !EVENT_TYPES.has(type)) return { ok: false, error: "unknown event type" };
  const ids = stepIds(plan);
  const ev = { type };

  if ("v" in body && body.v !== undefined) {
    if (!Number.isInteger(body.v) || body.v < 1) return { ok: false, error: "v must be a positive integer" };
    ev.v = body.v;
  } else ev.v = planVersion(plan);
  if (Number.isInteger(body.id)) ev.client_id = body.id;

  const text = (key, required) => {
    const val = body[key];
    if (val === undefined || val === null) { if (required) return `${key} is required`; return null; }
    if (typeof val !== "string") return `${key} must be a string`;
    const clean = stripControl(val);
    if (clean.length > MAX_TEXT_CHARS) return `${key} is longer than ${MAX_TEXT_CHARS} characters`;
    if (required && !clean.trim()) return `${key} is empty`;
    ev[key] = clean;
    return null;
  };
  const step = () => {
    if (typeof body.step !== "string" || !ids.has(body.step)) return "step is not in the current plan";
    ev.step = body.step;
    return null;
  };

  let err = null;
  switch (type) {
    case "step.review":
      err = step();
      if (!err && !(typeof body.status === "string" && REVIEW_STATUS.has(body.status))) err = "status must be approved, deferred or pending";
      if (!err) ev.status = body.status;
      if (!err) err = text("note", false);
      break;
    case "step.change_request":
      err = step() || text("text", true);
      break;
    case "step.edit": {
      err = step();
      if (!err) {
        const f = body.fields;
        if (!f || typeof f !== "object" || Array.isArray(f) || !Object.keys(f).length) err = "fields must be a non-empty object";
        else {
          ev.fields = {};
          for (const k of Object.keys(f)) {
            if (!EDIT_FIELDS.has(k)) { err = `unknown edit field ${k}`; break; }
            const val = f[k];
            if (typeof val === "string") {
              const clean = stripControl(val);
              if (clean.length > MAX_TEXT_CHARS) { err = `fields.${k} is longer than ${MAX_TEXT_CHARS} characters`; break; }
              ev.fields[k] = clean;
            } else if (Array.isArray(val) && val.every(x => typeof x === "string")) {
              const arr = val.map(stripControl);
              if (arr.join("\n").length > MAX_TEXT_CHARS) { err = `fields.${k} is longer than ${MAX_TEXT_CHARS} characters`; break; }
              ev.fields[k] = arr;
            } else { err = `fields.${k} must be a string or a list of strings`; break; }
          }
        }
      }
      break;
    }
    case "plan.change_request":
      err = text("text", true);
      break;
    case "plan.approved": {
      const m = body.steps;
      if (!m || typeof m !== "object" || Array.isArray(m)) err = "steps must be an object";
      else {
        ev.steps = {};
        for (const k of Object.keys(m)) {
          if (!ids.has(k)) { err = `step ${k} is not in the current plan`; break; }
          const st = typeof m[k] === "string" ? m[k] : (m[k] && m[k].status);
          if (!APPROVED_STATUS.has(st)) { err = `steps.${k} must be approved, deferred or edited`; break; }
          ev.steps[k] = st;
        }
      }
      break;
    }
    case "plan.rejected":
      err = text("reason", true);
      break;
  }
  if (err) return { ok: false, error: err };
  return { ok: true, event: ev };
}

function sendJson(res, status, obj, extra) {
  const body = JSON.stringify(obj);
  res.writeHead(status, Object.assign({ "Content-Type": "application/json; charset=utf-8",
                                        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" }, extra || {}));
  res.end(body);
}

function ownOrigin() { return `http://127.0.0.1:${port}`; }

function sameOrigin(req) {
  const origin = req.headers.origin;
  if (typeof origin !== "string" || origin !== ownOrigin()) return false;
  const sfs = req.headers["sec-fetch-site"];
  if (typeof sfs === "string" && sfs !== "same-origin" && sfs !== "none") return false;
  return true;
}

function readStateText() {
  try { return fs.readFileSync(STATE_FILE, "utf8"); } catch { return null; }
}

function currentState() {
  const raw = readStateText();
  if (raw !== null) {
    try { const obj = JSON.parse(raw); if (obj && typeof obj === "object") return obj; } catch {}
  }
  const plan = readPlan();
  return { version: planVersion(plan), status: (plan && typeof plan.status === "string") ? plan.status : "in_review", steps: {} };
}

function etagOf(text) { return `"${crypto.createHash("sha1").update(text).digest("hex").slice(0, 32)}"`; }

// Serve one of the three fixed plan files; the name is never taken from the URL.
function servePlanFile(res, name, type, transform) {
  const file = path.join(PLAN_DIR, name);
  if (!fs.existsSync(file) || !insideDir(PLAN_DIR, file) || !fs.statSync(file).isFile()) { sendJson(res, 404, { error: "not found" }); return; }
  let body = fs.readFileSync(file, "utf8");
  if (transform) body = transform(body);
  res.writeHead(200, { "Content-Type": type, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
  res.end(body);
}

function liveScript(plan) {
  const live = { v: planVersion(plan), token: TOKEN, base: planBase() };
  return `<script>window.__MAGICIAN_LIVE=${JSON.stringify(live).replace(/</g, "\\u003c")};</script>\n`;
}

function planBase() { return `${ownOrigin()}/magician/${PROJECT_NAME}/${TOKEN}/plan`; }

function handlePlan(req, res, url) {
  const prefix = `/magician/${PROJECT_NAME}/${TOKEN}/plan`;
  if (url !== prefix && !url.startsWith(prefix + "/")) { sendJson(res, 404, { error: "not found" }); return; }
  const route = url === prefix ? "" : url.slice(prefix.length + 1);
  const method = req.method;

  const only = (m) => { if (method === m) return true; res.writeHead(405, { Allow: m, "Content-Type": "application/json" }); res.end('{"error":"method not allowed"}'); return false; };

  switch (route) {
    case "":
      if (!only("GET")) return;
      servePlanFile(res, "plan.html", "text/html; charset=utf-8", html => {
        const plan = readPlan();
        const i = html.indexOf("</head>");
        return i < 0 ? liveScript(plan) + html : html.slice(0, i) + liveScript(plan) + html.slice(i);
      });
      return;
    case "plan.json":
      if (!only("GET")) return;
      servePlanFile(res, "plan.json", "application/json; charset=utf-8");
      return;
    case "plan.md":
      if (!only("GET")) return;
      servePlanFile(res, "plan.md", "text/markdown; charset=utf-8");
      return;
    case "state": {
      if (!only("GET")) return;
      const body = JSON.stringify(currentState());
      const tag = etagOf(body);
      if (req.headers["if-none-match"] === tag) { res.writeHead(304, { ETag: tag, "Cache-Control": "no-store" }); res.end(); return; }
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8", ETag: tag, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
      res.end(body);
      return;
    }
    case "events-stream":
      if (!only("GET")) return;
      openStream(req, res);
      return;
    case "events":
      if (!only("POST")) return;
      receiveEvent(req, res);
      return;
    default:
      sendJson(res, 404, { error: "not found" });
  }
}

function receiveEvent(req, res) {
  if (!sameOrigin(req)) { sendJson(res, 403, { error: "origin not allowed" }); return; }
  const ctype = String(req.headers["content-type"] || "").split(";")[0].trim().toLowerCase();
  if (ctype !== "application/json") { sendJson(res, 400, { error: "Content-Type must be application/json" }); return; }
  const declared = parseInt(req.headers["content-length"], 10);
  if (Number.isFinite(declared) && declared > MAX_EVENT_BYTES) {
    sendJson(res, 413, { error: `event larger than ${MAX_EVENT_BYTES} bytes` }, { Connection: "close" });
    req.resume();
    return;
  }
  const chunks = []; let size = 0; let done = false;
  req.on("data", c => {
    if (done) return;
    size += c.length;
    if (size > MAX_EVENT_BYTES) {
      done = true;
      sendJson(res, 413, { error: `event larger than ${MAX_EVENT_BYTES} bytes` }, { Connection: "close" });
      req.destroy();
      return;
    }
    chunks.push(c);
  });
  req.on("end", () => {
    if (done) return;
    done = true;
    let body;
    try { body = JSON.parse(Buffer.concat(chunks).toString("utf8")); } catch { sendJson(res, 400, { error: "body is not JSON" }); return; }
    const plan = readPlan();
    if (!plan) { sendJson(res, 400, { error: "plan.json is unreadable" }); return; }
    const v = validateEvent(body, plan);
    if (!v.ok) { sendJson(res, 400, { error: v.error }); return; }
    const rec = { id: crypto.randomUUID(), ts: new Date().toISOString(), ...v.event };
    try { fs.appendFileSync(EVENTS_FILE, JSON.stringify(rec) + "\n"); }
    catch { sendJson(res, 500, { error: "could not append the event" }); return; }
    touch();
    sendJson(res, 200, { id: rec.id });
  });
  req.on("error", () => { done = true; });
}

// SSE: one `data:` line per new events.jsonl line and per state.json change, from connection time on.
function openStream(req, res) {
  res.writeHead(200, { "Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-store", Connection: "keep-alive", "X-Accel-Buffering": "no" });
  res.write(": connected\n\n");
  const client = { res, offset: fileSize(EVENTS_FILE), partial: "", stateTag: etagOf(readStateText() || "") };
  sseClients.add(client);
  const ping = setInterval(() => { try { res.write(": ping\n\n"); } catch {} }, 15000);
  const close = () => { clearInterval(ping); sseClients.delete(client); };
  req.on("close", close);
  res.on("error", close);
}

function fileSize(file) { try { return fs.statSync(file).size; } catch { return 0; } }

function pumpStreams() {
  if (!sseClients.size) return;
  const size = fileSize(EVENTS_FILE);
  const stateText = readStateText();
  const stateTag = etagOf(stateText || "");
  for (const c of sseClients) {
    if (size < c.offset) { c.offset = 0; c.partial = ""; }   // file replaced
    if (size > c.offset) {
      let fd = null;
      try {
        fd = fs.openSync(EVENTS_FILE, "r");
        const buf = Buffer.alloc(size - c.offset);
        fs.readSync(fd, buf, 0, buf.length, c.offset);
        c.offset = size;
        const text = c.partial + buf.toString("utf8");
        const lines = text.split("\n");
        c.partial = lines.pop();
        for (const line of lines) if (line.trim()) { try { c.res.write(`data: ${line}\n\n`); } catch {} }
      } catch {} finally { if (fd !== null) try { fs.closeSync(fd); } catch {} }
    }
    if (stateTag !== c.stateTag) {
      c.stateTag = stateTag;
      let state = null;
      try { state = stateText === null ? null : JSON.parse(stateText); } catch {}
      if (state) { try { c.res.write(`data: ${JSON.stringify({ type: "state", state })}\n\n`); } catch {} }
    }
  }
}

// ─── HTTP server ─────────────────────────────────────────────────────────────

let port;

const server = http.createServer((req, res) => {
  touch();
  const url = req.url.split("?")[0];
  const query = Object.fromEntries(new URLSearchParams(req.url.split("?")[1] || ""));

  if (PLAN_MODE) {
    if (url === "/" || url === "") { res.writeHead(302, { Location: `${planBase()}/` }); res.end(); return; }
    handlePlan(req, res, url);
    return;
  }

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
    // A screen name is served only when it resolves inside this version's folder (no ../, no symlink out).
    if (!fs.existsSync(filepath) || !insideDir(vDir, filepath)) { serve404(res, `Screen not found: ${file}`); return; }
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

// ─── WebSocket (design mode) ─────────────────────────────────────────────────

server.on("upgrade", (req, socket) => {
  if (PLAN_MODE) { socket.destroy(); return; }
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

// ─── File watching ───────────────────────────────────────────────────────────

if (PLAN_MODE) {
  // events.jsonl / state.json → SSE clients. fs.watch gives the fast path; the 1 s poll is the
  // portable fallback (recursive/inotify limits, editors that replace files).
  try { fs.watch(STATE_DIR, () => { touch(); pumpStreams(); }); } catch {}
  setInterval(pumpStreams, 1000).unref();
} else {
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
  const drainOutbox = () => {
    let lines = [];
    try { lines = fs.readFileSync(OUTBOX_FILE, "utf8").split("\n").filter(Boolean); } catch { return; }
    for (const l of lines.slice(outboxCursor)) {
      try { const m = JSON.parse(l); broadcast({ type: m.type || "chat_reply", ...m }, m.version); } catch {}
    }
    outboxCursor = lines.length;
  };
  try {
    fs.watch(STATE_DIR, (event, filename) => { if (filename === "outbox.jsonl") { touch(); drainOutbox(); } });
  } catch {}
}

// ─── Start ───────────────────────────────────────────────────────────────────

function start(candidatePort) {
  server.once("error", err => {
    if (err.code === "EADDRINUSE") start(Math.floor(Math.random() * 16383) + 49152);
    else { console.error(err); process.exit(1); }
  });
  server.listen(candidatePort, "127.0.0.1", () => {
    port = server.address().port;
    if (PLAN_MODE) {
      const base = planBase();
      const info = {
        pid: process.pid, port, token: TOKEN, project: PROJECT_NAME,
        url_base: `${ownOrigin()}/magician/${PROJECT_NAME}/${TOKEN}`, plan_url: `${base}/`,
        plan_dir: PLAN_DIR, state_dir: STATE_DIR, events_file: EVENTS_FILE, state_file: STATE_FILE,
      };
      // One line on stdout, nothing else: vc-start.sh records it as <state>/server.json.
      process.stdout.write(JSON.stringify(info) + "\n");
      console.error(`✦ Magician Plan Companion → ${base}/`);
      return;
    }
    const urlBase = `http://localhost:${port}/magician/${PROJECT_NAME}`;
    const info = {
      port, project: PROJECT_NAME, url_base: urlBase, latest_url: `${urlBase}/v1/`,
      design_dir: DESIGN_DIR, screens_dir: SCREENS_DIR, state_dir: STATE_DIR,
      events_file: EVENTS_FILE, outbox_file: OUTBOX_FILE,
    };
    fs.writeFileSync(path.join(STATE_DIR, "server-info"), JSON.stringify(info, null, 2));
    console.log(`✦ Magician Design Companion → ${urlBase}/v1/`);
  });
}

start(Math.floor(Math.random() * 16383) + 49152);

// Auto-exit only when truly idle AND no browser is connected — so a long live design or review
// session (with a viewer open, or a /loop attached) is never killed mid-flow.
setInterval(() => {
  if (wsClients.size === 0 && sseClients.size === 0 && Date.now() - lastActivity > 90 * 60 * 1000) process.exit(0);
}, 60_000);

process.on("SIGTERM", () => process.exit(0));
process.on("SIGINT",  () => process.exit(0));
