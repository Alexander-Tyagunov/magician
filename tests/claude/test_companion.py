"""tools/companion/server.cjs in plan mode: the live review loop's transport (tools/companion/PROTOCOL.md).

`/blueprint` serves plan.html from a local token path; the page posts reviewer events and reads
state. This gate starts the real server (Node, skipped with a reason when `node` is absent) on a
temp copy of the valid plan fixture rendered by `tools/plan-render all`, and talks to it with
urllib only: the served page carries `window.__MAGICIAN_LIVE`, `GET state` has an ETag and answers
304, a valid POST appends one line with id/ts/v, oversized, unknown-type, unknown-step, foreign-origin,
wrong-token, non-JSON and wrong-method requests are refused with the documented status, control
characters are stripped from stored text, `..` and symlink escapes are 404, the event stream delivers
a new event within 3 s, and the server writes nothing but events.jsonl under the state folder.
`vc-start.sh --plan` prints the record and `vc-stop.sh` stops the process; the /conjure wrappers in
skills/conjure/scripts/ point at the moved files.
"""
from __future__ import annotations

import http.client
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[2]
COMPANION = ROOT / "tools" / "companion"
SERVER = COMPANION / "server.cjs"
RENDER = ROOT / "tools" / "plan-render"
FIXTURE = ROOT / "tests" / "claude" / "fixtures" / "plans" / "valid.json"
NODE = shutil.which("node")
BASH = "/bin/bash" if os.path.exists("/bin/bash") else (shutil.which("bash") or "bash")


def _snapshot(root: Path) -> dict:
    out = {}
    for p in root.rglob("*"):
        if p.is_file() or p.is_symlink():
            st = p.lstat()
            out[str(p.relative_to(root))] = (st.st_size, st.st_mtime_ns)
    return out


class _Server:
    """One plan-mode server on a temp tree; `base` is the page's LIVE.base (no trailing slash)."""

    def __init__(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="magician-companion-"))
        self.plan_dir = self.tmp / ".workspace" / "shared" / "plans" / "2026-11-01-demo"
        self.state_dir = self.tmp / ".workspace" / "local" / "plans" / "2026-11-01-demo" / "state"
        self.plan_dir.mkdir(parents=True)
        shutil.copy(FIXTURE, self.plan_dir / "plan.json")
        subprocess.run([str(RENDER), "all", str(self.plan_dir / "plan.json")], check=True,
                       capture_output=True, text=True, timeout=120)
        self.proc = subprocess.Popen([NODE, str(SERVER), "--plan", str(self.plan_dir), "demo", str(self.state_dir)],
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        line = self.proc.stdout.readline()
        self.info = json.loads(line)
        self.port = self.info["port"]
        self.origin = f"http://127.0.0.1:{self.port}"
        self.token = self.info["token"]
        self.base = f"{self.origin}/magician/demo/{self.token}/plan"
        self.plan = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def stop(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=10)
        self.proc.stdout.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def request(self, path: str, method: str = "GET", body=None, headers=None, origin=True):
        """(status, headers, body bytes); never raises on an HTTP error status."""
        data = None
        hdrs = dict(headers or {})
        if body is not None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
        if origin is True:
            hdrs.setdefault("Origin", self.origin)
        elif isinstance(origin, str):
            hdrs["Origin"] = origin
        url = path if path.startswith("http") else self.base + path
        req = urllib.request.Request(url, data=data,
                                     headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def events(self) -> list:
        f = self.state_dir / "events.jsonl"
        if not f.is_file():
            return []
        return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]


@unittest.skipIf(NODE is None, "node is not installed; the companion server needs Node >= 18")
class PlanServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.s = _Server()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.s.stop()

    # ---- serving ----

    def test_page_is_served_with_live_mode_injected(self) -> None:
        for path in ("/", ""):
            with self.subTest(path=path or "<base>"):
                status, headers, body = self.s.request(path)
                self.assertEqual(status, 200)
                self.assertIn("text/html", headers["Content-Type"])
                self.assertEqual(headers.get("Cache-Control"), "no-store")
                html = body.decode("utf-8")
                self.assertIn("window.__MAGICIAN_LIVE=", html)
                head = html.split("</head>", 1)[0]
                self.assertIn("__MAGICIAN_LIVE", head, "the live script must be injected before </head>")
                live = json.loads(head.split("window.__MAGICIAN_LIVE=", 1)[1].split(";</script>", 1)[0])
                self.assertEqual(live, {"v": self.s.plan["version"], "token": self.s.token, "base": self.s.base})
        # the file on disk is untouched (static review from file:// stays possible): the served page
        # carries exactly one more assignment than the file
        disk = (self.s.plan_dir / "plan.html").read_text(encoding="utf-8")
        self.assertEqual(html.count("window.__MAGICIAN_LIVE="), disk.count("window.__MAGICIAN_LIVE=") + 1)

    def test_plan_json_and_plan_md_are_served(self) -> None:
        status, headers, body = self.s.request("/plan.json")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["Content-Type"])
        self.assertEqual(json.loads(body)["version"], self.s.plan["version"])
        status, headers, body = self.s.request("/plan.md")
        self.assertEqual(status, 200)
        self.assertIn("text/markdown", headers["Content-Type"])
        self.assertEqual(body, (self.s.plan_dir / "plan.md").read_bytes())
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_state_has_an_etag_and_answers_304(self) -> None:
        status, headers, body = self.s.request("/state")
        self.assertEqual(status, 200)
        tag = headers["ETag"]
        self.assertTrue(tag.startswith('"') and tag.endswith('"'))
        state = json.loads(body)
        self.assertEqual(state["version"], self.s.plan["version"])
        self.assertEqual(state["status"], self.s.plan["status"])
        self.assertEqual(state["steps"], {})
        status, headers, body = self.s.request("/state", headers={"If-None-Match": tag})
        self.assertEqual(status, 304)
        self.assertEqual(body, b"")
        # Claude writes state.json; the ETag changes and the content is served verbatim
        (self.s.state_dir / "state.json").write_text('{"version": 1, "status": "in_review", "steps": {"T1": "revising"}, "hint": "hi"}', encoding="utf-8")
        try:
            status, headers2, body = self.s.request("/state", headers={"If-None-Match": tag})
            self.assertEqual(status, 200)
            self.assertNotEqual(headers2["ETag"], tag)
            self.assertEqual(json.loads(body)["steps"], {"T1": "revising"})
        finally:
            (self.s.state_dir / "state.json").unlink()

    def test_unknown_paths_wrong_token_and_escapes_are_404(self) -> None:
        wrong = f"{self.s.origin}/magician/demo/{'0' * 32}/plan/"
        outside = self.s.tmp / "secret.txt"
        outside.write_text("nope", encoding="utf-8")
        link = self.s.plan_dir / "plan.md"
        real = link.read_bytes()
        link.unlink()
        link.symlink_to(outside)
        try:
            for url in (wrong, wrong + "state", f"{self.s.origin}/magician/other/{self.s.token}/plan/",
                        self.s.base + "/../plan.json", self.s.base + "/plan.json/../plan.json",
                        self.s.base + "/%2e%2e/plan.json", self.s.base + "/history/plan.v1.json",
                        self.s.base + "/plan.html", self.s.base + "/nope", f"{self.s.origin}/magician/demo/",
                        f"{self.s.origin}/magician/demo/v1/", self.s.base + "/plan.md"):
                with self.subTest(url=url.replace(self.s.origin, "")):
                    status, headers, body = self.s.request(url)
                    self.assertEqual(status, 404)
                    self.assertNotIn(b"nope", body)
        finally:
            link.unlink()
            link.write_bytes(real)

    def test_wrong_method_is_405(self) -> None:
        status, headers, _ = self.s.request("/events")
        self.assertEqual(status, 405)
        self.assertEqual(headers.get("Allow"), "POST")
        for path in ("/", "/state", "/plan.json", "/plan.md", "/events-stream"):
            with self.subTest(path=path):
                status, headers, _ = self.s.request(path, method="POST", body={"type": "plan.change_request", "text": "x"})
                self.assertEqual(status, 405)
                self.assertEqual(headers.get("Allow"), "GET")

    def test_root_redirects_to_the_plan_page(self) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", self.s.port, timeout=10)
        conn.request("GET", "/")
        r = conn.getresponse()
        self.assertEqual(r.status, 302)
        self.assertEqual(r.getheader("Location"), self.s.base + "/")
        conn.close()

    # ---- POST events ----

    def test_valid_event_is_appended_with_id_ts_v(self) -> None:
        before = len(self.s.events())
        status, headers, body = self.s.request("/events", "POST",
                                               {"type": "step.review", "step": "T1", "status": "approved", "id": 7, "v": 1})
        self.assertEqual(status, 200, body)
        rid = json.loads(body)["id"]
        events = self.s.events()
        self.assertEqual(len(events), before + 1)
        rec = events[-1]
        self.assertEqual(list(rec)[:4], ["id", "ts", "type", "v"])
        self.assertEqual(rec["id"], rid)
        self.assertRegex(rec["id"], r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
        self.assertRegex(rec["ts"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
        self.assertEqual(rec["v"], 1)
        self.assertEqual(rec["client_id"], 7)
        self.assertEqual((rec["type"], rec["step"], rec["status"]), ("step.review", "T1", "approved"))

    def test_every_type_round_trips_and_v_defaults_to_the_plan_version(self) -> None:
        cases = [
            {"type": "step.change_request", "step": "T2", "text": "use redis"},
            {"type": "step.edit", "step": "T3", "fields": {"intent": "new intent", "files": ["a.py", "b.py"]}},
            {"type": "plan.change_request", "text": "re-plan around the queue"},
            {"type": "plan.approved", "steps": {"T1": "approved", "T2": {"status": "deferred"}, "T3": "edited"}},
            {"type": "plan.rejected", "reason": "wrong direction"},
        ]
        for ev in cases:
            with self.subTest(type=ev["type"]):
                status, _, body = self.s.request("/events", "POST", ev)
                self.assertEqual(status, 200, body)
                rec = self.s.events()[-1]
                self.assertEqual(rec["v"], self.s.plan["version"])
                self.assertEqual(rec["type"], ev["type"])
        rec = self.s.events()[-2]
        self.assertEqual(rec["steps"], {"T1": "approved", "T2": "deferred", "T3": "edited"})

    def test_unknown_keys_are_dropped_and_control_characters_stripped(self) -> None:
        ev = {"type": "step.change_request", "step": "T1", "text": "line\u0007 one\u0000\u001b[31m\ttab\nnext\u007f",
              "evil": "$(rm -rf /)", "__proto__": {"x": 1}}
        status, _, body = self.s.request("/events", "POST", ev)
        self.assertEqual(status, 200, body)
        rec = self.s.events()[-1]
        self.assertEqual(rec["text"], "line one[31m\ttab\nnext", "tab and newline stay; the rest goes")
        self.assertNotIn("evil", rec)
        self.assertEqual(set(rec), {"id", "ts", "type", "v", "step", "text"})

    def test_rejections(self) -> None:
        big = {"type": "plan.change_request", "text": "x" * 1500, "pad": "y" * 8000}
        cases = [
            ("over 8 KB", big, {}, True, 413),
            ("unknown type", {"type": "plan.deleted", "text": "x"}, {}, True, 400),
            ("missing type", {"text": "x"}, {}, True, 400),
            ("unknown step", {"type": "step.review", "step": "T99", "status": "approved"}, {}, True, 400),
            ("step not a string", {"type": "step.review", "step": ["T1"], "status": "approved"}, {}, True, 400),
            ("bad review status", {"type": "step.review", "step": "T1", "status": "merged"}, {}, True, 400),
            ("empty text", {"type": "step.change_request", "step": "T1", "text": "  "}, {}, True, 400),
            ("text over 2000", {"type": "step.change_request", "step": "T1", "text": "x" * 2001}, {}, True, 400),
            ("reason over 2000", {"type": "plan.rejected", "reason": "x" * 2001}, {}, True, 400),
            ("note over 2000", {"type": "step.review", "step": "T1", "status": "pending", "note": "x" * 2001}, {}, True, 400),
            ("unknown edit field", {"type": "step.edit", "step": "T1", "fields": {"verify_cmd": "rm"}}, {}, True, 400),
            ("empty edit", {"type": "step.edit", "step": "T1", "fields": {}}, {}, True, 400),
            ("approved with unknown step", {"type": "plan.approved", "steps": {"T99": "approved"}}, {}, True, 400),
            ("approved with bad status", {"type": "plan.approved", "steps": {"T1": "pending"}}, {}, True, 400),
            ("bad v", {"type": "plan.change_request", "text": "x", "v": "1"}, {}, True, 400),
            ("array body", [1, 2], {}, True, 400),
            ("non-JSON", b"not json", {}, True, 400),
            ("wrong content type", b'{"type":"plan.change_request","text":"x"}', {"Content-Type": "text/plain"}, True, 400),
            ("foreign origin", {"type": "plan.change_request", "text": "x"}, {}, "http://evil.example", 403),
            ("localhost origin", {"type": "plan.change_request", "text": "x"}, {}, f"http://localhost:{self.s.port}", 403),
            ("no origin", {"type": "plan.change_request", "text": "x"}, {}, False, 403),
            ("cross-site fetch", {"type": "plan.change_request", "text": "x"}, {"Sec-Fetch-Site": "cross-site"}, True, 403),
        ]
        before = len(self.s.events())
        for name, body, headers, origin, want in cases:
            with self.subTest(case=name):
                status, _, resp = self.s.request("/events", "POST", body, headers=headers, origin=origin)
                self.assertEqual(status, want, resp)
                self.assertIn("error", json.loads(resp))
        self.assertEqual(len(self.s.events()), before, "a rejected event was stored")

    def test_oversized_body_without_content_length_is_413(self) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", self.s.port, timeout=10)
        path = self.s.base.replace(self.s.origin, "") + "/events"
        conn.putrequest("POST", path)
        conn.putheader("Origin", self.s.origin)
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Transfer-Encoding", "chunked")
        conn.endheaders()
        chunk = b'{"type":"plan.change_request","text":"' + b"x" * 9000 + b'"}'
        try:
            conn.send(b"%x\r\n" % len(chunk) + chunk + b"\r\n0\r\n\r\n")
            r = conn.getresponse()
            self.assertEqual(r.status, 413)
        except (ConnectionResetError, BrokenPipeError, http.client.RemoteDisconnected):
            pass  # the server closed the connection on the oversized body: also a refusal
        finally:
            conn.close()
        self.assertFalse([e for e in self.s.events() if len(e.get("text", "")) >= 9000])

    def test_step_check_uses_the_current_plan(self) -> None:
        plan_file = self.s.plan_dir / "plan.json"
        original = plan_file.read_text(encoding="utf-8")
        plan = json.loads(original)
        plan["steps"] = plan["steps"][:1]
        plan_file.write_text(json.dumps(plan), encoding="utf-8")
        try:
            status, _, _ = self.s.request("/events", "POST", {"type": "step.review", "step": "T2", "status": "approved"})
            self.assertEqual(status, 400)
        finally:
            plan_file.write_text(original, encoding="utf-8")
        status, _, _ = self.s.request("/events", "POST", {"type": "step.review", "step": "T2", "status": "approved"})
        self.assertEqual(status, 200)

    # ---- SSE ----

    def test_event_stream_delivers_a_new_event_within_3_s(self) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", self.s.port, timeout=10)
        conn.request("GET", self.s.base.replace(self.s.origin, "") + "/events-stream")
        r = conn.getresponse()
        self.assertEqual(r.status, 200)
        self.assertIn("text/event-stream", r.getheader("Content-Type"))
        self.assertNotIn("Access-Control-Allow-Origin", dict(r.getheaders()))
        sock = conn.sock
        sock.settimeout(3)
        status, _, body = self.s.request("/events", "POST", {"type": "step.change_request", "step": "T4", "text": "stream me"})
        self.assertEqual(status, 200)
        rid = json.loads(body)["id"]
        t0 = time.monotonic()
        buf = b""
        data = None
        while time.monotonic() - t0 < 3 and data is None:
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk
            for line in buf.split(b"\n"):
                if line.startswith(b"data: ") and rid.encode() in line:
                    data = json.loads(line[6:])
        self.assertIsNotNone(data, f"no event on the stream within 3 s: {buf[:300]!r}")
        self.assertEqual(data["id"], rid)
        self.assertEqual(data["text"], "stream me")
        # a state.json change is mirrored too
        (self.s.state_dir / "state.json").write_text('{"version": 1, "status": "in_review", "steps": {"T4": "revising"}}', encoding="utf-8")
        try:
            t0 = time.monotonic()
            got = None
            while time.monotonic() - t0 < 3 and got is None:
                try:
                    chunk = sock.recv(65536)
                except socket.timeout:
                    break
                if not chunk:
                    break
                buf += chunk
                for line in buf.split(b"\n"):
                    if line.startswith(b'data: {"type":"state"'):
                        got = json.loads(line[6:])
            self.assertIsNotNone(got, "no state change on the stream within 3 s")
            self.assertEqual(got["state"]["steps"], {"T4": "revising"})
        finally:
            (self.s.state_dir / "state.json").unlink()
            conn.close()

    # ---- footprint ----

    def test_server_writes_only_events_jsonl(self) -> None:
        s = _Server()
        try:
            before = _snapshot(s.tmp)
            s.request("/")
            s.request("/state")
            s.request("/plan.json")
            s.request("/plan.md")
            s.request("/events", "POST", {"type": "plan.change_request", "text": "footprint"})
            s.request("/events", "POST", {"type": "plan.bogus"})
            s.request(s.base + "/../x")
            time.sleep(0.3)
            after = _snapshot(s.tmp)
        finally:
            s.stop()
        changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        self.assertEqual(changed, {str(Path(".workspace/local/plans/2026-11-01-demo/state/events.jsonl"))})
        self.assertEqual(set(after) - set(before), {str(Path(".workspace/local/plans/2026-11-01-demo/state/events.jsonl"))})

    def test_server_binds_loopback_only(self) -> None:
        table = Path("/proc/net/tcp")
        if not table.is_file():
            self.skipTest("no /proc/net/tcp to inspect listeners")
        rows = [l.split() for l in table.read_text().splitlines()[1:]]
        listening = [r[1] for r in rows if r[3] == "0A" and r[1].endswith(f":{self.s.port:04X}")]
        self.assertTrue(listening, "listener not found")
        self.assertEqual({r.split(":")[0] for r in listening}, {"0100007F"}, "must bind 127.0.0.1 only")

    def test_sources(self) -> None:
        text = SERVER.read_text(encoding="utf-8")
        self.assertNotIn("Access-Control-Allow", text, "no CORS headers, ever")
        self.assertIn('"127.0.0.1"', text)
        self.assertNotIn("require(", text.replace('require("http")', "").replace('require("fs")', "")
                         .replace('require("path")', "").replace('require("crypto")', ""), "no dependencies")
        self.assertTrue((COMPANION / "PROTOCOL.md").is_file())
        for name in ("helper.js", "frame-template.html", "vc-start.sh", "vc-stop.sh"):
            self.assertTrue((COMPANION / name).is_file(), name)


@unittest.skipIf(NODE is None, "node is not installed; the companion server needs Node >= 18")
class StartStopScriptTests(unittest.TestCase):
    def test_vc_start_plan_prints_the_record_and_vc_stop_stops_it(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="magician-vc-"))
        try:
            plan_dir = tmp / ".workspace" / "shared" / "plans" / "2026-11-01-demo"
            plan_dir.mkdir(parents=True)
            shutil.copy(FIXTURE, plan_dir / "plan.json")
            subprocess.run([str(RENDER), "all", str(plan_dir / "plan.json")], check=True, capture_output=True, timeout=120)
            rel = ".workspace/shared/plans/2026-11-01-demo"
            proc = subprocess.run([BASH, str(COMPANION / "vc-start.sh"), rel, "demo", "--plan"], cwd=tmp,
                                  capture_output=True, text=True, timeout=60, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            info = json.loads(proc.stdout)
            state_dir = tmp / ".workspace" / "local" / "plans" / "2026-11-01-demo" / "state"
            try:
                for key in ("pid", "port", "token", "url_base", "plan_url", "state_dir", "events_file", "state_file"):
                    self.assertIn(key, info)
                self.assertEqual(info["plan_url"], f"http://127.0.0.1:{info['port']}/magician/demo/{info['token']}/plan/")
                self.assertEqual(info["state_dir"], ".workspace/local/plans/2026-11-01-demo/state")
                self.assertEqual(info["events_file"], ".workspace/local/plans/2026-11-01-demo/state/events.jsonl")
                self.assertRegex(info["token"], r"^[0-9a-f]{32}$")
                self.assertEqual(json.loads((state_dir / "server.json").read_text(encoding="utf-8")), info)
                self.assertEqual((state_dir / "server.pid").read_text().strip(), str(info["pid"]))
                self.assertEqual((state_dir / ".gitignore").read_text(), "*\n")
                self.assertFalse((plan_dir / "screens").exists(), "plan mode must not create design folders")
                with urllib.request.urlopen(info["plan_url"], timeout=10) as r:
                    self.assertIn("__MAGICIAN_LIVE", r.read().decode("utf-8"))
            finally:
                stop = subprocess.run([BASH, str(COMPANION / "vc-stop.sh"), rel], cwd=tmp,
                                      capture_output=True, text=True, timeout=30, check=False)
            self.assertIn("stopped", stop.stdout)
            for _ in range(50):
                try:
                    os.kill(info["pid"], 0)
                except OSError:
                    break
                time.sleep(0.1)
            else:
                os.kill(info["pid"], signal.SIGKILL)
                self.fail("vc-stop.sh did not stop the server")
            self.assertFalse((state_dir / "server.pid").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_vc_start_refuses_a_folder_without_plan_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run([BASH, str(COMPANION / "vc-start.sh"), tmp, "demo", "--plan"],
                                  capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("plan.json", proc.stderr)
            self.assertEqual(proc.stdout, "")


class ConjureWrapperTests(unittest.TestCase):
    """The /conjure skill grants `${CLAUDE_SKILL_DIR}/scripts/vc-start.sh *`; those paths stay."""

    def test_wrappers_point_at_the_moved_companion(self) -> None:
        scripts = ROOT / "skills" / "conjure" / "scripts"
        for name in ("vc-start.sh", "vc-stop.sh"):
            with self.subTest(script=name):
                p = scripts / name
                text = p.read_text(encoding="utf-8")
                self.assertTrue(os.access(p, os.X_OK), f"{name} is not executable")
                self.assertLessEqual(len(text.splitlines()), 5)
                self.assertIn(f"tools/companion/{name}", text)
                self.assertEqual(subprocess.run([BASH, "-n", str(p)], capture_output=True).returncode, 0)
        cjs = (scripts / "server.cjs").read_text(encoding="utf-8")
        self.assertLessEqual(len(cjs.splitlines()), 3)
        self.assertIn('require("../../../tools/companion/server.cjs")', cjs)
        for name in ("helper.js", "frame-template.html"):
            self.assertFalse((scripts / name).exists(), f"{name} moved to tools/companion/")

    def test_wrapper_runs_the_real_script(self) -> None:
        proc = subprocess.run([BASH, str(ROOT / "skills" / "conjure" / "scripts" / "vc-stop.sh"), "/nonexistent/dir"],
                              capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "not running")


if __name__ == "__main__":
    unittest.main()
