"""tools/plan-render — plan.json in, plan.md + plan.html out, deterministically and offline.

`/blueprint` writes plan.json once; `plan-render` validates it and renders the two documents every
consumer reads. These tests pin the contract:
  * `check` accepts the valid fixtures (and the skill's worked example) and refuses each invalid
    case in fixtures/plans/invalid-cases.json with exit 2 and one line naming the rule it broke;
  * `md` and `html` are byte-identical to the snapshots in fixtures/plans/ (same JSON ⇒ same bytes,
    no timestamps), the Task blocks keep the legacy shape /orchestrate parses, and the trailer
    carries the version and the sha256 of the canonical JSON;
  * the page inlines the plan with `</` escaped, carries the CSP, references nothing remote, and
    pre-renders the plan document (Markdown subset + wave-graph SVG) without a runtime library;
  * charts render only where the plan has the data;
  * `diff` summarises changed fields per step id and added/removed steps;
  * `--transport local|artifact|static|auto` picks how the page's toolbar reaches the session; the
    page carries the live (companion) code path, the artifact (`claude.use("db")`) code path guarded
    by the capability resolving, and the static chat-line fallback;
  * `workflow` emits a Claude Code Workflow script (snapshot `valid.workflow.js`): `meta` first, one
    phase per wave, parallel() then sequential agent() calls in dependency order, deferred steps
    omitted, no Date.now()/Math.random()/new Date()/import() outside strings, `node --check` clean;
  * `all` writes plan.md, plan.html, plan.workflow.js and history/plan.v<n>.json next to the json,
    refuses an invalid plan without writing, and refuses a version older than the newest history
    snapshot.
"""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "plan-render"
FIX = ROOT / "tests" / "claude" / "fixtures" / "plans"
VALID = FIX / "valid.json"
ONE_WAVE = FIX / "one-wave.json"
EXAMPLE = ROOT / "skills" / "blueprint" / "references" / "plan-example.json"

# One file holds every invalid case: {"<name>": {"expect": "<substring every violation line for it must
# contain>", and exactly one of "patch": [{"path": [key|index, …], "set": value} | {"path": …, "delete":
# true}, …] (applied to valid.json, in order), "plan": {...} (the whole plan) or "raw": "<text>" (for
# input that is not JSON a dict can hold — NaN, duplicate keys, broken syntax)}}. Each case is written
# to a temp plan.json and checked as is. Patches keep the file small (29 whole plans would be ~790 KB,
# over the gate's 256 KiB per-file limit) and make each case's single mutation readable.
INVALID_CASES = FIX / "invalid-cases.json"
CASES = json.loads(INVALID_CASES.read_text(encoding="utf-8"))
INVALID = {name: case["expect"] for name, case in CASES.items()}
CASE_FORMS = ("patch", "plan", "raw")
BAD_TYPES_LINES = ("research: must be a list of strings", "context.stack: must be a list of strings",
                   "context.blast[6]: must be {path: string, files: int, hits: int}",
                   "context.edges[13]: must be {from: id, to: id}", "step T2: field 'touches' must be a list")


@contextlib.contextmanager
def case_file(name: str):
    """Write invalid case `name` to a temp plan.json and yield its path."""
    case = CASES[name]
    if "raw" in case:
        text = case["raw"]
    else:
        plan = case["plan"] if "plan" in case else load(VALID)
        for op in case.get("patch", ()):
            *head, last = op["path"]
            node = plan
            for key in head:
                node = node[key]
            if op.get("delete"):
                del node[last]
            else:
                node[last] = op["set"]
        text = json.dumps(plan, ensure_ascii=False)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "plan.json"
        path.write_text(text, encoding="utf-8")
        yield path


def check_json(plan: dict, *args: str) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "plan.json"
        path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        return run("check", str(path), *args)


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True,
                          cwd=str(cwd or ROOT), timeout=120)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def page_without_plan_content(html: str) -> str:
    """The page minus the blocks that carry plan text verbatim (the inlined JSON, the raw plan.md
    string and the pre-rendered plan document), so a URL in a step's prose does not count as a
    resource reference."""
    html = re.sub(r'<script type="application/json" id="plan">.*?</script>', "", html, flags=re.S)
    html = re.sub(r'<script type="application/json" id="plan-md-raw">.*?</script>', "", html, flags=re.S)
    html = re.sub(r'<template id="plan-md">.*?</template>', "", html, flags=re.S)
    return html


class CheckTests(unittest.TestCase):
    def test_valid_fixtures_and_the_skills_example_pass(self) -> None:
        for path in (VALID, ONE_WAVE, EXAMPLE):
            with self.subTest(plan=path.name):
                p = run("check", str(path))
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                self.assertTrue(p.stdout.startswith("ok: "), p.stdout)
                self.assertEqual(p.stderr, "", "a consistent plan must not warn")

    def test_every_invalid_fixture_fails_with_the_rule_it_broke(self) -> None:
        self.assertGreaterEqual(len(INVALID), 25)
        self.assertEqual(sorted(p.name for p in FIX.glob("invalid-*.json")), ["invalid-cases.json"])
        for name, case in CASES.items():
            forms = [k for k in CASE_FORMS if k in case]
            self.assertEqual(len(forms), 1, f"{name}: needs exactly one of {CASE_FORMS}")
            self.assertEqual(sorted(case), sorted({forms[0], "expect"}), name)
            if forms[0] == "patch":
                self.assertTrue(case["patch"], f"{name}: an empty patch is the valid plan")
                for op in case["patch"]:
                    self.assertTrue(op.get("path") and ("set" in op) != bool(op.get("delete")), f"{name}: {op}")
        for name, needle in INVALID.items():
            with self.subTest(fixture=name):
                with case_file(name) as path:
                    p = run("check", str(path))
                self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                self.assertIn(needle, p.stdout)
                self.assertIn("violation(s)", p.stderr)
                self.assertTrue(all(line.strip() for line in p.stdout.splitlines()), "one line per violation")
        with case_file("bad-types") as path:
            p = run("check", str(path))
        for line in BAD_TYPES_LINES:
            self.assertIn(line, p.stdout)

    def test_strict_json(self) -> None:
        for text, needle in (('{"a": NaN}', "NaN is not valid JSON"), ('{"a": Infinity}', "Infinity"),
                             ('{"a": 1, "a": 2}', "duplicate key 'a'")):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "plan.json"
                path.write_text(text, encoding="utf-8")
                p = run("check", str(path))
            with self.subTest(text=text):
                self.assertEqual(p.returncode, 2)
                self.assertIn("not valid JSON", p.stderr)
                self.assertIn(needle, p.stderr)

    def test_wrong_types_never_traceback(self) -> None:
        plan = load(VALID)
        cases = [("steps", "x"), ("waves", None), ("context", []), ("constraints", "x"), ("sources", "x"),
                 ("version", 10001), ("version", "1"), ("version", True), ("spec", 3)]
        for key, value in cases:
            bad = dict(plan, **{key: value})
            p = check_json(bad)
            with self.subTest(field=key):
                self.assertEqual(p.returncode, 2, p.stderr)
                self.assertNotIn("Traceback", p.stderr)
        step_cases = {"depends_on": "T1", "touches": "render", "files": [], "red": "x", "green": None, "verify": "x",
                      "risk": [], "effort": 5, "review": "pending", "parallel": "yes", "history": {}, "screens": "x",
                      "infographic": {"type": "bar", "title": "t", "data": [["a", 1]] * 7}}
        for key, value in step_cases.items():
            bad = load(VALID)
            bad["steps"][0][key] = value
            p = check_json(bad)
            with self.subTest(step_field=key):
                self.assertEqual(p.returncode, 2, p.stderr)
                self.assertNotIn("Traceback", p.stderr)
                self.assertIn("step T1", p.stdout + p.stderr)
        for comp in ("x", {"id": "__proto__", "layer": "a", "label": "b"}, {"id": "a b", "layer": "a", "label": "b"}):
            bad = load(VALID)
            bad["context"]["components"].append(comp)
            p = check_json(bad)
            with self.subTest(component=str(comp)):
                self.assertEqual(p.returncode, 2)
                self.assertIn("context.components[", p.stdout)
        for cmd in ("rm --recursive x", "find . -name '*.pyc' -delete", "curl x | " + "sh", "terraform destroy",
                    "kubectl delete pod", "git push origin +main"):
            bad = load(VALID)
            bad["steps"][0]["verify"].append(cmd)
            with self.subTest(cmd=cmd):
                self.assertIn("destructive command form", check_json(bad).stdout)
        bad = load(VALID)
        bad["steps"][1]["files"]["create"] = ["C:\\x.py", "~/x.py", "/etc/x"]
        self.assertEqual(check_json(bad).stdout.count("must be relative to the project root"), 3)

    def test_dependency_on_a_deferred_step_warns(self) -> None:
        plan = load(VALID)
        plan["steps"][0]["review"]["status"] = "deferred"
        p = check_json(plan)
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn("warning: step T3: depends on T1, which is deferred", p.stderr)

    def test_hostile_plan_text_is_escaped_everywhere(self) -> None:
        plan = load(VALID)
        plan["title"] = '@@PLAN_JSON@@ <img src=x onerror=alert(1)> & "quotes" — ünïcode @@PLAN_MD_RAW@@'
        s = plan["steps"][0]
        s["title"] = "</script><script>alert(2)</script> @@TITLE@@ <!-- x"
        s["intent"] = "Line one & <b>bold</b> \"q\" 's' @@CHARTS@@\n<!-- not a comment --> `tick` $(pwd) \\back"
        s["red"]["code"] = 'assert "</script>" not in html\nassert 1 == 1'
        s["green"]["sketch"] = "line a\nline b <i>x</i>"
        s["review"] = {"status": "edited", "note": "", "edited_text": "use `argparse` groups\nsecond line"}
        plan["context"]["components"][0]["label"] = "<svg onload=alert(3)>"
        plan["context"]["summary"] = "<!-- open comment"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            p = run("html", str(path))
            md = run("md", str(path)).stdout
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        html = p.stdout
        rest = page_without_plan_content(html)
        for bad in ("<img", "<svg onload", "onerror=alert(1)>", "<script>alert(2)", "alert(2)</script>", "<b>bold", "<i>x</i>"):
            self.assertNotIn(bad, rest, bad)
        self.assertIn("<h1 id=\"title\">@@PLAN_JSON@@ &lt;img src=x onerror=alert(1)&gt; &amp; &quot;quotes&quot;", html)
        self.assertEqual(html.count("@@PLAN_JSON@@"), 5, "title tag, h1, dialog h1, raw md, json — never expanded")
        m = re.search(r'<script type="application/json" id="plan">(.*?)</script>', html, re.S)
        self.assertEqual(json.loads(m.group(1)), plan, "the inlined JSON round-trips")
        tpl = re.search(r'<template id="plan-md">(.*?)</template>', html, re.S).group(1)
        self.assertIn("<h3>Task 1: &lt;/script&gt;&lt;script&gt;alert(2)&lt;/script&gt; @@TITLE@@ &lt;!-- x (T1)</h3>", tpl)
        self.assertIn("<p>&lt;!-- open comment</p>", tpl, "an unterminated comment never swallows the document")
        self.assertIn("<h3>Task 12:", tpl)
        self.assertIn('<pre><code>assert &quot;&lt;/script&gt;&quot; not in html\nassert 1 == 1</code></pre>', tpl)
        self.assertIn("<blockquote><p>use &#x27;argparse&#x27; groups second line</p></blockquote>", tpl)
        self.assertIn('- [ ] Commit: `git commit -m "feat: /scriptscriptalert(2)/script @@TITLE@@ -- x"`', md)
        self.assertIn("**Reviewer edit:**\n> use 'argparse' groups\n> second line\n", md)
        self.assertIn("**Test code:**\n\n```\nassert \"</script>\" not in html\nassert 1 == 1\n```", md)
        self.assertIn("- [ ] Implement: see the implementation sketch below", md)

    def test_md_and_html_refuse_an_invalid_plan(self) -> None:
        for cmd in ("md", "html"):
            with self.subTest(cmd=cmd):
                with case_file("unresolved-dep") as path:
                    p = run(cmd, str(path))
                self.assertEqual(p.returncode, 2)
                self.assertEqual(p.stdout, "step T3: depends_on 'T99' does not resolve to a step id\n")
                self.assertIn("nothing rendered", p.stderr)

    def test_oversized_plan_is_refused(self) -> None:
        plan = load(VALID)
        plan["steps"][0]["intent"] = "x" * (257 * 1024)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            p = run("check", str(path))
        self.assertEqual(p.returncode, 2)
        self.assertIn("size: plan.json is", p.stdout)
        self.assertIn("256 KiB", p.stdout)

    def test_inconsistent_metrics_warn_but_do_not_fail(self) -> None:
        plan = load(VALID)
        plan["metrics"]["steps"] = 99
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            p = run("check", str(path))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("warning: metrics.steps: plan says 99, steps give 12", p.stderr)

    def test_not_json_is_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text("{not json", encoding="utf-8")
            p = run("check", str(path))
        self.assertEqual(p.returncode, 2)
        self.assertIn("not valid JSON", p.stderr)


class MdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.md = run("md", str(VALID)).stdout

    def test_snapshot_is_byte_identical(self) -> None:
        self.assertEqual(self.md, (FIX / "valid.md").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "plan.md"
            p = run("md", str(VALID), "-o", str(out))
            self.assertEqual((p.returncode, p.stdout), (0, ""))
            self.assertEqual(out.read_bytes(), (FIX / "valid.md").read_bytes())
            self.assertEqual(stat.S_IMODE(out.stat().st_mode) & 0o044, 0o044, "rendered files are readable like specs")

    def test_task_blocks_keep_the_legacy_shape(self) -> None:
        plan = load(VALID)
        heads = re.findall(r"^### Task (\d+): (.*) \((T\d+)\)$", self.md, re.M)
        self.assertEqual([(int(n), t, i) for n, t, i in heads],
                         [(k + 1, s["title"], s["id"]) for k, s in enumerate(plan["steps"])])
        blocks = re.split(r"^### Task \d+: ", self.md, flags=re.M)[1:]
        for block in blocks:
            with self.subTest(task=block.splitlines()[0]):
                lines = block.splitlines()
                self.assertRegex(lines[1], r"^Parallel: (YES|NO)( \(depends on Task \d+(, Task \d+)*\))?$")
                self.assertIn("**Files:**", lines)
                i = lines.index("**Files:**")
                self.assertTrue(lines[i + 1].startswith("- Create: "))
                self.assertTrue(lines[i + 2].startswith("- Modify: "))
                self.assertTrue(lines[i + 3].startswith("- Test: "))
                self.assertEqual([l.split(":")[0] for l in lines if l.startswith("- [ ] ")],
                                 ["- [ ] Write failing test", "- [ ] Run test", "- [ ] Implement",
                                  "- [ ] Run test", "- [ ] Commit"])
                self.assertRegex(block, r"(?m)^- \[ \] Run test: verify FAIL — `.+`$")
                self.assertRegex(block, r"(?m)^- \[ \] Run test: verify PASS — `.+`$")
                self.assertRegex(block, r"(?m)^- \[ \] Commit: `git commit -m \"feat: .+\"`$")
                self.assertRegex(block, r"(?m)^Review: (pending|approved|deferred|edited|changed)")

    def test_header_sections_and_trailer(self) -> None:
        plan = load(VALID)
        self.assertTrue(self.md.startswith(f"# Plan: {plan['title']}\n\nVersion: v1 · Status: in_review · Spec: `"))
        self.assertIn("\n## Global Constraints\n_Every task inherits these — do not restate per task._\n- "
                      + plan["constraints"][0] + "\n", self.md)
        self.assertIn("\n## Waves\n\n- W1 Foundations: T1 (parallel), T2 (parallel)\n", self.md)
        self.assertIn("```mermaid\ngraph LR\n", self.md)
        self.assertIn("\n  T1 --> T3\n", self.md)
        self.assertNotIn("## Deferred", self.md, "nothing is deferred in the valid fixture")
        canonical = json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        import hashlib
        self.assertTrue(self.md.endswith(f"<!-- magician.plan/1 v1 sha256:{hashlib.sha256(canonical).hexdigest()} -->\n"))

    def test_deferred_and_edited_steps(self) -> None:
        plan = load(VALID)
        plan["steps"][3]["review"] = {"status": "deferred", "note": "next sprint", "edited_text": ""}
        plan["steps"][1]["review"] = {"status": "edited", "note": "", "edited_text": "Use argparse groups."}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            md = run("md", str(path)).stdout
        head, deferred = md.split("\n## Deferred — not executed this run\n")
        self.assertNotIn("### Task 4:", head)
        self.assertIn("### Task 4: ", deferred, "a deferred step keeps its number")
        self.assertIn("\nReview: deferred (next sprint)\n", deferred)
        self.assertIn("\nReview: edited\n\n**Reviewer edit:**\n> Use argparse groups.\n", head)
        self.assertIn("- W2 Renderers: T3 (parallel), T4 (deferred), T5 (sequential), T6 (sequential)\n", head)
        self.assertRegex(md, r"<!-- magician\.plan/1 v1 sha256:[0-9a-f]{64} -->\n$")


class HtmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = run("html", str(VALID)).stdout
        cls.plan = load(VALID)

    def test_snapshot_is_byte_identical_and_deterministic(self) -> None:
        self.assertEqual(self.html, (FIX / "valid.html").read_text(encoding="utf-8"))
        self.assertEqual(run("html", str(VALID)).stdout, self.html)
        self.assertLess(len(self.html.encode("utf-8")), 256 * 1024)

    def test_plan_is_inlined_with_closing_tags_escaped(self) -> None:
        m = re.search(r'<script type="application/json" id="plan">(.*?)</script>', self.html, re.S)
        self.assertIsNotNone(m)
        body = m.group(1)
        self.assertNotIn("</", body)
        self.assertNotIn("<!--", body)
        self.assertIn("<\\/", body, "the fixture carries a '</' that must be escaped as '<\\/'")
        self.assertEqual(json.loads(body), self.plan, "the escaped form decodes back to the plan")
        raw = re.search(r'<script type="application/json" id="plan-md-raw">(.*?)</script>', self.html, re.S).group(1)
        self.assertNotIn("</", raw)
        self.assertEqual(json.loads(raw), run("md", str(VALID)).stdout)

    def test_csp_and_no_remote_resources(self) -> None:
        self.assertIn('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src '
                      '\'unsafe-inline\'; script-src \'unsafe-inline\'; img-src data:; connect-src http://127.0.0.1:*">',
                      self.html)
        rest = page_without_plan_content(self.html)
        urls = [u for u in re.findall(r"https?://[^\s\"'<>)]*", rest) if u != "http://127.0.0.1:*"]
        self.assertEqual(urls, [], f"remote reference in the page: {urls[:5]}")
        self.assertNotRegex(rest, r"<script[^>]*\bsrc=")
        self.assertNotRegex(rest, r"<link\b")
        self.assertNotIn("@import", rest)
        self.assertNotIn("@font-face", rest)
        self.assertNotIn("cdn.jsdelivr", self.html)
        self.assertNotIn("mermaid.min.js", self.html)

    def test_plan_document_is_prerendered(self) -> None:
        m = re.search(r'<template id="plan-md">(.*?)</template>', self.html, re.S)
        self.assertIsNotNone(m)
        tpl = m.group(1)
        self.assertIn("<h1>Plan: ", tpl)
        self.assertEqual(tpl.count("<h3>Task "), len(self.plan["steps"]))
        self.assertIn('<svg class="wavegraph"', tpl)
        self.assertNotIn("```", tpl)
        self.assertNotIn("class=\"mermaid\"", tpl)
        self.assertIn('<li class="task"><input type="checkbox" disabled> Write failing test:', tpl)
        self.assertIn("<table><thead><tr><th>Blast radius</th>", tpl)
        self.assertIn("<em>Every task inherits these — do not restate per task.</em>", tpl)
        self.assertIn('<pre><code class="language-diff">', tpl)
        for s in self.plan["steps"]:
            self.assertIn(f'data-step="{s["id"]}"', tpl)
        self.assertEqual(tpl.count('class="dep"'), sum(len(s["depends_on"]) for s in self.plan["steps"]))

    def test_static_mode_and_live_code_paths(self) -> None:
        self.assertIn('data-review="auto"', self.html)
        self.assertIn('data-review="static"', run("html", str(VALID), "--static").stdout)
        self.assertIn("window.__MAGICIAN_LIVE", self.html)
        for route in ("liveUrl('events')", "liveUrl('state')", "liveUrl('events-stream')", "liveUrl('plan.json')"):
            self.assertIn(route, self.html, f"companion route {route} (tools/companion/PROTOCOL.md)")
        self.assertIn("Static — this page cannot reach the session; reply in chat", self.html)
        self.assertNotIn("Math.random", self.html, "no simulated Claude replies")
        self.assertIn("This page is static: the reason is copied as a chat line `plan: rejected — <reason>` for you to paste; nothing is archived from here.", self.html)
        self.assertIn('<span class="chip" id="tally" aria-live="polite">', self.html)
        self.assertIn("function nextPlayable", self.html, "Play skips deferred steps")
        self.assertIn('<dt><span class="kbd">?</span></dt><dd>This help</dd>', self.html)
        self.assertIn('<h2 aria-live="polite">', self.html)
        self.assertIn("function trap(e)", self.html, "dialogs trap focus")

    def test_transport_flag(self) -> None:
        for t in ("local", "artifact", "static", "auto"):
            self.assertIn(f'data-review="{t}"', run("html", str(VALID), "--transport", t).stdout)
        self.assertIn('data-review="static"', run("html", str(VALID), "--transport", "local", "--static").stdout,
                      "--static wins over --transport")
        self.assertEqual(run("html", str(VALID), "--transport", "comments").returncode, 2)
        # auto: live when the companion injected __MAGICIAN_LIVE, else artifact when claude.use exists, else static
        self.assertIn("const MODE=root.dataset.review||'auto'", self.html)
        self.assertIn("(MODE==='auto'||MODE==='local')&&window.__MAGICIAN_LIVE", self.html)
        self.assertIn("(MODE==='auto'||MODE==='artifact')&&!!(window.claude&&typeof window.claude.use==='function')", self.html)
        self.assertNotRegex(self.html, r"window\.claude\.(db|room|artifact)\b", "only claude.use is promised by the host")

    def test_live_mode_page_behaviour_is_present(self) -> None:
        # §6.2 events are POSTed, not composed as chat lines, when live
        for ev in ("'step.review'", "'step.change_request'", "'step.edit'", "'plan.change_request'",
                   "'plan.approved'", "'plan.rejected'"):
            self.assertIn(ev, self.html)
        self.assertIn("method:'POST'", self.html)
        self.assertIn("body.length>8192", self.html, "the 8 KB cap is enforced page-side too")
        # revising ring with elapsed time, aria-busy, the 10-minute "waiting" notice
        self.assertIn("card.setAttribute('aria-busy',busy?'true':'false')", self.html)
        self.assertIn('id="elapsed"', self.html)
        self.assertIn("const WAIT_MS=600000", self.html)
        self.assertIn("Waiting for Claude — check the session", self.html)
        # polling cadence and the stream
        self.assertIn("revising?2000:10000", self.html)
        self.assertIn("'if-none-match'", self.html)
        self.assertIn("r.status===304", self.html)
        self.assertIn("new EventSource(liveUrl('events-stream'))", self.html)
        # hot-swap: version gate, per-step diff in plan-render diff's field order, v<n> badge, what-changed panel
        self.assertIn("if(ver>PLAN.version) loadPlan(ver)", self.html)
        self.assertIn("function stepDiff(a,b)", self.html)
        self.assertIn("Object.keys(Object.assign({},fa,fb)).sort()", self.html, "same flattening + sorted order as `plan-render diff`")
        self.assertIn('data-badge="version"', self.html)
        self.assertIn("What changed (v", self.html)
        self.assertIn("s.review.status='changed'", self.html)
        # stale events dropped with a notice; state.hint/notice/messages land in the transcript
        self.assertIn("Ignored a stale ", self.html)
        self.assertIn("Not sent — the plan moved to v", self.html)
        for k in ("st.hint", "st.notice", "st.messages", "st.revising", "st.changed", "st.steps"):
            self.assertIn(k, self.html)
        self.assertIn("type:'plan.approved',steps:map", self.html)
        self.assertIn("type:'plan.rejected',reason:r", self.html)
        self.assertNotIn("location.reload", self.html, "revisions are hot-swapped, never reloaded")

    def test_artifact_transport_code_paths_are_guarded_by_claude_use(self) -> None:
        self.assertIn("window.claude.use('db').then(db=>{", self.html)
        self.assertIn("if(!db){link.kind='static'", self.html, "null ⇒ static fallback")
        self.assertIn("Artifact without a database — reply in chat", self.html)
        self.assertIn("link.db.collection('events').add(doc)", self.html, "one document per event")
        self.assertIn("db.doc('state/current').onSnapshot(", self.html)
        self.assertIn("db.doc('plan/current').onSnapshot(", self.html)
        self.assertEqual(self.html.count(".onSnapshot("), 2, "subscribe once per document, never in render")
        self.assertNotIn("onSnapshot", self.html.split("function renderDetail")[1].split("/* ---------- player")[0])
        self.assertIn("link.queue=link.queue.then(", self.html, "one write at a time")
        self.assertIn("code==='invalid_argument'", self.html)
        self.assertIn("setReadOnly(", self.html)
        self.assertIn("},10000)", self.html, "10 s loading timer")
        self.assertIn("snap.metadata.fromCache", self.html)
        script = self.html.split("<script>\n(function(){")[-1]
        self.assertNotIn("declare_capabilities", script)
        self.assertNotIn("capabilities:", script, "the page declares nothing itself (the skill does, via the Artifact tool)")
        self.assertNotIn("token", self.html.split("function startArtifact")[1].split("function chatLine")[0],
                         "no secrets go to the database")

    def test_theme_option(self) -> None:
        self.assertIn('<html lang="en" data-theme="light" data-theme-mode="auto"', self.html)
        self.assertIn('data-theme="dark" data-theme-mode="dark"', run("html", str(VALID), "--theme", "dark").stdout)
        self.assertIn('data-theme="light" data-theme-mode="light"', run("html", str(VALID), "--theme", "light").stdout)
        p = run("html", str(VALID), "--theme", "sepia")
        self.assertEqual(p.returncode, 2)

    def test_layers_are_generic_and_come_from_components(self) -> None:
        layers = []
        for c in self.plan["context"]["components"]:
            if c["layer"] not in layers:
                layers.append(c["layer"])
        self.assertEqual(layers, ["skills", "tools", "docs", "lore", "tests"])
        self.assertNotIn("layer-skills", self.html, "no hard-coded layer names in the template")
        for i in range(1, 7):
            self.assertIn(f"--l-{i}:", self.html)

    def test_charts_render_only_where_data_exists(self) -> None:
        def charts(html: str) -> list[str]:
            block = re.search(r'<div id="charts" aria-hidden="true">(.*?)</div>\n<template', html, re.S).group(1)
            return re.findall(r'<div class="chart" data-chart="([^"]+)">', block)

        full = charts(self.html)
        self.assertEqual(full[:6], ["tasks_per_wave", "parallel_vs_sequential", "effort_by_layer",
                                    "blast_radius", "critical_path", "risk_matrix"])
        self.assertEqual(full[6:], ["step:" + s["id"] for s in self.plan["steps"] if "infographic" in s])
        one = charts(run("html", str(ONE_WAVE)).stdout)
        self.assertNotIn("tasks_per_wave", one, "one wave: nothing to compare")
        self.assertNotIn("blast_radius", one, "kg blast did not run")
        self.assertNotIn("critical_path", one, "fewer than 3 steps")
        self.assertNotIn("risk_matrix", one, "no medium/high risk")
        self.assertEqual(one, ["parallel_vs_sequential", "effort_by_layer"])

    def test_every_chart_has_a_title_desc_and_data_table(self) -> None:
        block = re.search(r'<div id="charts" aria-hidden="true">(.*?)</div>\n<template', self.html, re.S).group(1)
        charts = re.findall(r'<div class="chart" data-chart="[^"]+">(.*?)</table></div>', block, re.S)
        self.assertEqual(len(charts), block.count('<div class="chart"'))
        for c in charts:
            self.assertEqual(c.count("<svg"), 1)
            self.assertIn("<title id=", c)
            self.assertIn("<desc id=", c)
            self.assertIn('</svg><table class="sr"><caption>', c)

    def test_mermaid_flag_falls_back_without_mmdc(self) -> None:
        env = dict(os.environ, PATH="/nonexistent")
        p = subprocess.run([sys.executable, str(TOOL), "html", str(VALID), "--mermaid"], env=env,
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, self.html, "without mmdc on PATH --mermaid renders the same page")


class DiffTests(unittest.TestCase):
    def test_summary_lists_changed_fields_added_and_removed_steps(self) -> None:
        a = load(VALID)
        b = json.loads(json.dumps(a))
        b["version"] = 2
        b["status"] = "in_review"
        b["steps"][2]["intent"] = "rewritten"
        b["steps"][2]["red"]["run"] = "pytest -k md"
        b["steps"][4]["files"]["modify"].append("tools/extra")
        removed = b["steps"].pop(11)
        b["waves"][3]["steps"].remove(removed["id"])
        b["steps"].append({**a["steps"][0], "id": "T13", "wave": "W4"})
        b["waves"][3]["steps"].append("T13")
        with tempfile.TemporaryDirectory() as tmp:
            pa, pb = Path(tmp) / "a.json", Path(tmp) / "b.json"
            pa.write_text(json.dumps(a), encoding="utf-8")
            pb.write_text(json.dumps(b), encoding="utf-8")
            p = run("diff", str(pa), str(pb))
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout)
        self.assertEqual(out, {"from": 1, "to": 2, "added": ["T13"], "removed": ["T12"],
                               "changed": {"T3": ["intent", "red.run"], "T5": ["files.modify"]},
                               "plan": ["version", "waves"]})

    def test_identical_plans_diff_to_nothing(self) -> None:
        out = json.loads(run("diff", str(VALID), str(VALID)).stdout)
        self.assertEqual(out, {"from": 1, "to": 1, "added": [], "removed": [], "changed": {}, "plan": []})


FORBIDDEN_JS = ("Date.now(", "Math.random(", "new Date(", "import(")


def js_code_only(src: str) -> str:
    """The script minus string literals and comments (a crude but sufficient scan for the tests)."""
    src = re.sub(r"//[^\n]*", "", src)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', src)
    src = re.sub(r"'(?:[^'\\\n]|\\.)*'", "''", src)
    src = re.sub(r"`(?:[^`\\]|\\.)*`", "``", src, flags=re.S)
    return src


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.out = run("workflow", str(VALID)).stdout
        cls.plan = load(VALID)

    def test_snapshot_is_byte_identical_and_deterministic(self) -> None:
        self.assertEqual(self.out, (FIX / "valid.workflow.js").read_text(encoding="utf-8"))
        self.assertEqual(run("workflow", str(VALID)).stdout, self.out)

    def test_meta_is_the_first_statement_and_a_literal(self) -> None:
        self.assertTrue(self.out.startswith("export const meta = {\n  name: \"plan-walkthrough-static-plan\",\n  description: "))
        meta = self.out.split("\n}\n", 1)[0]
        self.assertNotIn("${", meta)
        self.assertNotRegex(meta, r"\b(args|process|require)\b")
        for w in self.plan["waves"]:
            self.assertIn(f'{{ title: "{w["id"]} {w["title"]}", detail: ', meta)

    def test_one_phase_per_wave_parallel_then_sequential_in_dependency_order(self) -> None:
        phases = re.findall(r'^phase\("([^"]+)"\)$', self.out, re.M)
        self.assertEqual(phases, [f'{w["id"]} {w["title"]}' for w in self.plan["waves"]])
        by = {s["id"]: s for s in self.plan["steps"]}
        for w in self.plan["waves"]:
            block = self.out.split(f'phase("{w["id"]} {w["title"]}")', 1)[1].split("\nphase(", 1)[0]
            par = re.findall(r'^  \(\) => task\("(T\d+)"', block, re.M)
            seq = re.findall(r'^await task\("(T\d+)"', block, re.M)
            self.assertEqual(sorted(par), sorted(s for s in w["steps"] if by[s]["parallel"]))
            self.assertEqual(sorted(seq), sorted(s for s in w["steps"] if not by[s]["parallel"]))
            if par:
                self.assertLess(block.index("await parallel(["), block.index("await task(") if seq else len(block))
            for i, sid in enumerate(seq):
                for dep in by[sid]["depends_on"]:
                    if dep in seq:
                        self.assertLess(seq.index(dep), i, f"{sid} must come after {dep}")
            self.assertIn(f'log("{w["id"]} {w["title"]} done")', block)
        self.assertEqual(self.out.count("await parallel(["), sum(1 for w in self.plan["waves"] if any(by[s]["parallel"] for s in w["steps"])))

    def test_every_prompt_carries_the_task_block_and_demands_the_bounded_schema(self) -> None:
        md = run("md", str(VALID)).stdout
        for s in self.plan["steps"]:
            n = [i + 1 for i, x in enumerate(self.plan["steps"]) if x["id"] == s["id"]][0]
            heading = f"### Task {n}: {s['title']} ({s['id']})"
            self.assertIn(heading, md)
            self.assertIn(json.dumps(heading + "\n", ensure_ascii=False), self.out)
            self.assertIn(json.dumps(f'RETURN JSON: {{task:"{s["id"]}" (Task {n}), green (bool), commit (sha or subject), '
                                     f'files_changed[], summary (≤ 1200 chars, distilled — no logs), obstacles[] '
                                     '(lore/obstacles.md fields: STATUS, OBSTACLE, BLOCKER, SEVERITY, WORKAROUND, RECURRENCE, SCOPE, NEXT; empty when clean)}', ensure_ascii=False), self.out)
        for c in self.plan["constraints"]:
            self.assertIn(json.dumps(f"- {c}\n", ensure_ascii=False), self.out)
        self.assertIn("summary: S(1200)", self.out)
        self.assertIn("files_changed: FILES", self.out)
        for f in ("STATUS", "OBSTACLE", "BLOCKER", "SEVERITY", "WORKAROUND", "RECURRENCE", "SCOPE", "NEXT"):
            self.assertIn(f"{f}:", self.out)
        self.assertIn("schema: RESULT", self.out)
        self.assertIn("stallMs: STALL_MS", self.out)
        self.assertIn("label: id", self.out)
        self.assertIn("'- [ ] Write failing test:'" if False else "- [ ] Write failing test:", self.out)

    def test_forbidden_runtime_tokens_are_absent_outside_strings(self) -> None:
        code = js_code_only(self.out)
        for tok in FORBIDDEN_JS:
            self.assertNotIn(tok, code)
        # a plan whose prose carries the tokens still renders (they sit inside strings) and node parses it
        plan = load(VALID)
        plan["steps"][0]["intent"] += ' mention Date.now() and new Date() and import("x") and a `tick ${x}`'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            p = run("workflow", str(path))
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertNotIn("Date.now(", js_code_only(p.stdout))
            self.assertIn("mention Date.now()", p.stdout)

    def test_balanced_and_node_check_clean(self) -> None:
        code = js_code_only(self.out)
        for o, c in ("()", "[]", "{}"):
            self.assertEqual(code.count(o), code.count(c), f"unbalanced {o}{c}")
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        wrapped = self.out.split("\n}\n", 1)
        src = wrapped[0] + "\n}\nasync function __workflow(args, budget, agent, parallel, pipeline, phase, log) {\n" + wrapped[1] + "}\n"
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "plan.workflow.mjs"
            f.write_text(src, encoding="utf-8")
            p = subprocess.run([node, "--check", str(f)], capture_output=True, text=True, timeout=60)
            self.assertEqual(p.returncode, 0, p.stderr)

    def test_deferred_steps_are_omitted(self) -> None:
        plan = load(VALID)
        for s in plan["steps"]:
            if s["id"] == "T5":
                s["review"]["status"] = "deferred"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            p = run("workflow", str(path))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn('task("T5"', p.stdout)
        self.assertNotIn("### Task 5:", p.stdout)
        self.assertIn("// Deferred — not executed this run: T5", p.stdout)
        self.assertIn('deferred: ["T5"]', p.stdout)
        self.assertIn("11 tasks in 4 waves, 1 deferred", p.stdout)
        self.assertIn("Note: T5 is deferred this run; treat its outputs as absent.", p.stdout)
        self.assertEqual(re.findall(r'^await task\("(T\d+)"', p.stdout.split('phase("W2 Renderers")')[1].split("\nphase(")[0], re.M), ["T4", "T6"])

    def test_workflow_refuses_an_invalid_plan_and_writes_with_dash_o(self) -> None:
        with case_file("unresolved-dep") as path:
            p = run("workflow", str(path))
        self.assertEqual(p.returncode, 2)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "plan.workflow.js"
            p = run("workflow", str(VALID), "-o", str(out))
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(out.read_text(encoding="utf-8"), self.out)


class AllTests(unittest.TestCase):

    def test_all_prints_short_paths_through_a_symlinked_folder(self) -> None:
        # macOS: the working folder resolves to /private/var while the argument says /var.
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real" / "2026-11-01-feature"
            real.mkdir(parents=True)
            link = Path(tmp) / "link"
            link.symlink_to(Path(tmp) / "real", target_is_directory=True)
            shutil.copy(VALID, real / "plan.json")
            p = run("all", str(link / "2026-11-01-feature" / "plan.json"), cwd=real)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertEqual(p.stdout.splitlines()[0], "plan.md")
    def test_all_writes_three_files_and_a_history_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "2026-11-01-feature"
            folder.mkdir()
            shutil.copy(VALID, folder / "plan.json")
            p = run("all", str(folder / "plan.json"), cwd=folder)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertEqual(p.stdout.splitlines(), ["plan.md", "plan.html", "plan.workflow.js", os.path.join("history", "plan.v1.json")])
            self.assertEqual((folder / "plan.md").read_bytes(), (FIX / "valid.md").read_bytes())
            self.assertEqual((folder / "plan.html").read_bytes(), (FIX / "valid.html").read_bytes())
            self.assertEqual((folder / "plan.workflow.js").read_bytes(), (FIX / "valid.workflow.js").read_bytes())
            self.assertEqual((folder / "history" / "plan.v1.json").read_bytes(), VALID.read_bytes())
            self.assertEqual(sorted(x.name for x in folder.iterdir()), ["history", "plan.html", "plan.json", "plan.md", "plan.workflow.js"])
            # a revision: v2 snapshots next to v1; an older version is refused once v2 exists
            plan = load(VALID)
            plan["version"] = 2
            (folder / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
            p = run("all", str(folder / "plan.json"), "--static", "--theme", "dark", cwd=folder)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertTrue((folder / "history" / "plan.v2.json").exists())
            self.assertIn('data-review="static"', (folder / "plan.html").read_text(encoding="utf-8"))
            shutil.copy(VALID, folder / "plan.json")
            p = run("all", str(folder / "plan.json"), cwd=folder)
            self.assertEqual(p.returncode, 2)
            self.assertIn("version: v1 is lower than history/plan.v2.json", p.stdout)
            # the same v2 bytes render again; different v2 bytes are refused until the version is bumped
            (folder / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
            self.assertEqual(run("all", str(folder / "plan.json"), cwd=folder).returncode, 0)
            plan["title"] = "changed"
            (folder / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
            before = (folder / "plan.md").read_bytes()
            p = run("all", str(folder / "plan.json"), cwd=folder)
            self.assertEqual(p.returncode, 2)
            self.assertIn("history/plan.v2.json already holds a different v2; bump the version", p.stdout)
            self.assertEqual((folder / "plan.md").read_bytes(), before, "nothing written")
            # a linked history/ folder is refused
            shutil.rmtree(folder / "history")
            (Path(tmp) / "elsewhere").mkdir()
            (folder / "history").symlink_to(Path(tmp) / "elsewhere")
            p = run("all", str(folder / "plan.json"), cwd=folder)
            self.assertEqual(p.returncode, 2)
            self.assertIn("history/ is a symbolic link", p.stdout)
            self.assertEqual(list((Path(tmp) / "elsewhere").iterdir()), [])

    def test_all_refuses_an_invalid_plan_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with case_file("unresolved-dep") as path:
                shutil.copy(path, folder / "plan.json")
            p = run("all", str(folder / "plan.json"), cwd=folder)
            self.assertEqual(p.returncode, 2)
            self.assertIn("nothing rendered", p.stderr)
            self.assertEqual([x.name for x in folder.iterdir()], ["plan.json"])


class CliTests(unittest.TestCase):
    def test_help_and_usage(self) -> None:
        p = run("--help")
        self.assertEqual(p.returncode, 0)
        for cmd in ("check", "md", "html", "workflow", "diff", "all"):
            self.assertIn(f"plan-render {cmd} ", p.stdout)
        self.assertIn("--theme light|dark|auto", p.stdout)
        self.assertIn("--transport auto|local|artifact|static", p.stdout)
        self.assertIn("--static", p.stdout)
        self.assertIn("--mermaid", p.stdout)
        p = run()
        self.assertEqual(p.returncode, 64)
        p = run("check", str(FIX / "does-not-exist.json"))
        self.assertEqual(p.returncode, 1)
        self.assertIn("cannot read", p.stderr)

    def test_tool_is_executable_stdlib_python_under_200_kib(self) -> None:
        self.assertTrue(os.access(TOOL, os.X_OK))
        src = TOOL.read_text(encoding="utf-8")
        self.assertTrue(src.startswith("#!/usr/bin/env python3\n\"\"\"magician plan-render"))
        self.assertLess(TOOL.stat().st_size, 200 * 1024)
        imports = set(re.findall(r"^(?:import|from) (\w+)", src, re.M))
        self.assertTrue(imports <= {"__future__", "argparse", "hashlib", "html", "json", "os", "re", "shutil",
                                    "subprocess", "sys", "tempfile", "math"}, imports)


if __name__ == "__main__":
    unittest.main()
