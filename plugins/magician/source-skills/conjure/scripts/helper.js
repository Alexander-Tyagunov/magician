(function () {
  "use strict";

  const PORT    = window.__VC_PORT;
  const VERSION = window.__VC_VERSION;
  const PROJECT = (location.pathname.split("/")[2]) || window.__VC_PROJECT || "project";
  const CHAT_ON = !!window.__VC_CHAT;
  const BASE    = `/magician/${PROJECT}/v${VERSION}`;
  let ws;

  // ─── selection locator: a stable-ish handle for any clicked element ──────────
  function locate(el) {
    if (!el || el === document.body) return { selector: "body", tag: "body" };
    if (el.dataset && el.dataset.mid) return { mid: el.dataset.mid, selector: `[data-mid="${el.dataset.mid}"]`, tag: el.tagName.toLowerCase() };
    if (el.id) return { id: el.id, selector: `#${el.id}`, tag: el.tagName.toLowerCase() };
    // build a short CSS path (max 4 hops) with :nth-of-type for stability
    const parts = [];
    let node = el;
    for (let i = 0; node && node.nodeType === 1 && i < 4 && node !== document.body; i++) {
      let seg = node.tagName.toLowerCase();
      const cls = (node.className && typeof node.className === "string")
        ? node.className.trim().split(/\s+/).filter(c => !/^__vc/.test(c))[0] : null;
      if (cls) seg += "." + cls;
      const parent = node.parentElement;
      if (parent) {
        const sib = Array.from(parent.children).filter(c => c.tagName === node.tagName);
        if (sib.length > 1) seg += `:nth-of-type(${sib.indexOf(node) + 1})`;
      }
      parts.unshift(seg);
      node = node.parentElement;
    }
    const r = el.getBoundingClientRect();
    return {
      selector: parts.join(" > "),
      tag: el.tagName.toLowerCase(),
      text: (el.textContent || "").trim().slice(0, 80),
      rect: { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) },
    };
  }

  function connect() {
    ws = new WebSocket(`ws://localhost:${PORT}/magician/${PROJECT}/v${VERSION}/`);
    ws.onopen  = function () { updateBar("connected", "#10b981"); };
    ws.onclose = function () { updateBar("reconnecting…", "#f59e0b"); setTimeout(connect, 1500); };
    ws.onerror = function () { ws.close(); };
    ws.onmessage = function (e) {
      let msg; try { msg = JSON.parse(e.data); } catch { return; }
      if (msg.type === "reload") { location.reload(); return; }
      if (msg.type === "new_version") {
        const bar = document.getElementById("__vc_bar");
        if (bar) {
          bar.innerHTML = `<span style="color:#a78bfa;cursor:pointer">✦ New prototype ready — click to open →</span>`;
          bar.onclick = function () { location.href = msg.url; };
        }
        return;
      }
      if (msg.type === "chat_ack")   { chatWorking(true); return; }
      if (msg.type === "chat_reply") { chatWorking(false); chatAppend("claude", msg.text || ""); return; }
      if (msg.type === "toast")      { updateBar(msg.text || "", "#a78bfa"); return; }
    };
  }

  function send(msg) { if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg)); }

  function updateBar(text, color) {
    const bar = document.getElementById("__vc_selection");
    if (bar) { bar.textContent = text; if (color) bar.style.color = color; }
  }

  // ─── click / selection capture ──────────────────────────────────────────────
  document.addEventListener("click", function (e) {
    if (e.target.closest && e.target.closest("#__vc_chat")) return; // ignore our own UI
    const choiceEl = e.target.closest("[data-choice]");
    if (choiceEl) {
      const container  = choiceEl.closest("[data-multiselect]");
      const choiceKey  = choiceEl.dataset.choice;
      const choiceText = choiceEl.dataset.text || choiceEl.textContent.trim().slice(0, 80);
      if (container) { choiceEl.classList.toggle("selected"); }
      else {
        const group = choiceEl.closest(".approaches, [data-group]");
        if (group) group.querySelectorAll("[data-choice]").forEach(c => c.classList.remove("selected"));
        choiceEl.classList.add("selected");
      }
      updateBar(`Selected: ${choiceText}`, "#a78bfa");
      send({ type: "click", choice: choiceKey, text: choiceText, target: locate(choiceEl), timestamp: Date.now() });
    } else {
      // general "what did the user click" — a stable locator the session can act on
      send({ type: "selection", target: locate(e.target), text: (e.target.textContent || "").trim().slice(0, 80), timestamp: Date.now() });
    }
  });

  window.vcToggle = function (el) {
    el.classList.toggle("selected");
    send({ type: "click", choice: el.dataset.choice, text: el.dataset.text || el.textContent.trim().slice(0, 80), target: locate(el), timestamp: Date.now() });
  };

  connect();

  // ─── status bar (full-doc mockups) ───────────────────────────────────────────
  if (!document.getElementById("__vc_bar")) {
    const bar = document.createElement("div");
    bar.id = "__vc_bar";
    bar.style.cssText = "position:fixed;bottom:0;left:0;right:0;z-index:9999;padding:8px 20px;font:12px/1 'JetBrains Mono',monospace;background:rgba(10,10,15,0.9);backdrop-filter:blur(8px);border-top:1px solid #1e1e2e;display:flex;align-items:center;gap:12px;color:#64748b";
    bar.innerHTML = `<span style="color:#7c3aed;font-weight:700">✦ Magician</span> <span style="color:#1e1e2e">|</span> <span id="__vc_selection">waiting…</span>`;
    document.body.appendChild(bar);
  }

  // ─── companion chat widget (opt-in via window.__VC_CHAT) ─────────────────────
  let chatOpen = false;
  function chatWorking(on) {
    const s = document.getElementById("__vc_chat_status");
    if (s) s.textContent = on ? "Claude is working…" : "";
  }
  function chatAppend(who, text) {
    const log = document.getElementById("__vc_chat_log");
    if (!log) return;
    const row = document.createElement("div");
    row.style.cssText = "margin:6px 0;font:13px/1.4 system-ui,sans-serif";
    row.innerHTML = `<span style="color:${who === "you" ? "#7c3aed" : "#10b981"};font-weight:600">${who === "you" ? "You" : "✦ Claude"}</span><br><span style="color:#cbd5e1"></span>`;
    row.querySelector("span:last-child").textContent = text;
    log.appendChild(row); log.scrollTop = log.scrollHeight;
  }
  function buildChat() {
    if (document.getElementById("__vc_chat")) return;
    const wrap = document.createElement("div");
    wrap.id = "__vc_chat";
    wrap.innerHTML = `
      <button id="__vc_chat_btn" title="Talk to Claude about this design"
        style="position:fixed;bottom:56px;right:20px;z-index:10000;width:52px;height:52px;border-radius:50%;border:none;cursor:pointer;background:linear-gradient(135deg,#7c3aed,#a78bfa);color:#fff;font-size:22px;box-shadow:0 6px 24px rgba(124,58,237,.5)">✦</button>
      <div id="__vc_chat_panel" style="display:none;position:fixed;bottom:120px;right:20px;z-index:10000;width:340px;max-width:calc(100vw - 40px);height:420px;max-height:70vh;background:#0f0f18;border:1px solid #2a2a3e;border-radius:14px;box-shadow:0 12px 48px rgba(0,0,0,.6);display:flex;flex-direction:column;overflow:hidden">
        <div style="padding:12px 14px;background:rgba(124,58,237,.15);border-bottom:1px solid #2a2a3e;font:600 13px system-ui;color:#e2e8f0;display:flex;justify-content:space-between;align-items:center">
          <span>✦ Talk to Claude</span><span id="__vc_chat_close" style="cursor:pointer;color:#64748b">✕</span>
        </div>
        <div id="__vc_chat_log" style="flex:1;overflow-y:auto;padding:12px 14px"></div>
        <div id="__vc_chat_status" style="padding:0 14px;font:12px system-ui;color:#f59e0b;min-height:16px"></div>
        <div style="padding:10px;border-top:1px solid #2a2a3e;display:flex;gap:8px">
          <input id="__vc_chat_input" placeholder="e.g. move the title up a bit" autocomplete="off"
            style="flex:1;background:#1a1a28;border:1px solid #2a2a3e;border-radius:8px;padding:9px 11px;color:#e2e8f0;font:13px system-ui;outline:none">
          <button id="__vc_chat_send" style="background:#7c3aed;border:none;border-radius:8px;color:#fff;padding:0 14px;cursor:pointer;font:600 13px system-ui">↑</button>
        </div>
      </div>`;
    document.body.appendChild(wrap);
    const panel = document.getElementById("__vc_chat_panel");
    const input = document.getElementById("__vc_chat_input");
    const toggle = (show) => { chatOpen = show; panel.style.display = show ? "flex" : "none"; if (show) input.focus(); };
    document.getElementById("__vc_chat_btn").onclick = () => toggle(!chatOpen);
    document.getElementById("__vc_chat_close").onclick = () => toggle(false);
    function submit() {
      const text = input.value.trim(); if (!text) return;
      input.value = ""; chatAppend("you", text); chatWorking(true);
      // include whatever the user last clicked so "move THIS" has context
      fetch(`${BASE}/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) })
        .catch(() => { chatWorking(false); chatAppend("claude", "(couldn't reach the session — is it still running?)"); });
    }
    document.getElementById("__vc_chat_send").onclick = submit;
    input.addEventListener("keydown", e => { if (e.key === "Enter") submit(); });
    chatAppend("claude", "Ask me to tweak this design — I'll update it live. (Replies appear when your Claude session is engaged.)");
  }
  if (CHAT_ON) buildChat();
})();
