(function () {
  "use strict";

  const PORT    = window.__VC_PORT;
  const VERSION = window.__VC_VERSION;
  let ws;

  function connect() {
    ws = new WebSocket(`ws://localhost:${PORT}/magician/${location.pathname.split("/")[2]}/${VERSION}/`);
    ws.onopen    = function () { updateBar("connected", "#10b981"); };
    ws.onclose   = function () { updateBar("reconnecting…", "#f59e0b"); setTimeout(connect, 1500); };
    ws.onerror   = function () { ws.close(); };
    ws.onmessage = function (e) {
      const msg = JSON.parse(e.data);
      if (msg.type === "reload") location.reload();
      if (msg.type === "new_version") {
        const bar = document.getElementById("__vc_bar");
        if (bar) {
          bar.textContent = `✦ New prototype ready → ${msg.url}`;
          bar.style.background = "rgba(124,58,237,0.3)";
          bar.style.color = "#a78bfa";
          bar.style.cursor = "pointer";
          bar.onclick = function () { location.href = msg.url; };
        }
      }
    };
  }

  function send(msg) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
  }

  function updateBar(text, color) {
    const bar = document.getElementById("__vc_selection");
    if (bar) { bar.textContent = text; if (color) bar.style.color = color; }
  }

  // Click capture — looks for nearest [data-choice] ancestor
  document.addEventListener("click", function (e) {
    const el = e.target.closest("[data-choice]");
    if (!el) return;

    const container  = el.closest("[data-multiselect]");
    const choiceKey  = el.dataset.choice;
    const choiceText = el.dataset.text || el.textContent.trim().slice(0, 80);

    if (container) {
      el.classList.toggle("selected");
    } else {
      const siblings = el.closest(".approaches, [data-group]");
      if (siblings) siblings.querySelectorAll("[data-choice]").forEach(c => c.classList.remove("selected"));
      el.classList.add("selected");
    }

    updateBar(`Selected: ${choiceText}`, "#a78bfa");
    send({ type: "click", choice: choiceKey, text: choiceText, timestamp: Date.now() });
  });

  // Expose for inline onclick use
  window.vcToggle = function (el) {
    el.classList.toggle("selected");
    send({ type: "click", choice: el.dataset.choice, text: el.dataset.text || el.textContent.trim().slice(0, 80), timestamp: Date.now() });
  };

  connect();

  // Inject floating bar if not present in frame-template (for full-doc mockups)
  if (!document.getElementById("__vc_bar")) {
    const bar = document.createElement("div");
    bar.id = "__vc_bar";
    bar.style.cssText = "position:fixed;bottom:0;left:0;right:0;z-index:9999;padding:8px 20px;font:12px/1 'JetBrains Mono',monospace;background:rgba(10,10,15,0.9);backdrop-filter:blur(8px);border-top:1px solid #1e1e2e;display:flex;align-items:center;gap:12px;color:#64748b";
    bar.innerHTML = `<span style="color:#7c3aed;font-weight:700">✦ Magician</span> <span style="color:#1e1e2e">|</span> <span id="__vc_selection">waiting…</span>`;
    document.body.appendChild(bar);
  }
})();
