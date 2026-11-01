"""tools/plan-render — plan.json in, plan.md + plan.html out, deterministically and offline.

`/blueprint` writes plan.json once; `plan-render` validates it and renders the two documents every
consumer reads. These tests pin the contract:
  * `check` accepts the valid fixtures (and the skill's worked example) and refuses each invalid
    fixture with exit 2 and one line naming the rule it broke;
  * `md` and `html` are byte-identical to the snapshots in fixtures/plans/ (same JSON ⇒ same bytes,
    no timestamps), the Task blocks keep the legacy shape /orchestrate parses, and the trailer
    carries the version and the sha256 of the canonical JSON;
  * the page inlines the plan with `</` escaped, carries the CSP, references nothing remote, and
    pre-renders the plan document (Markdown subset + wave-graph SVG) without a runtime library;
  * charts render only where the plan has the data;
  * `diff` summarises changed fields per step id and added/removed steps;
  * `all` writes plan.md, plan.html and history/plan.v<n>.json next to the json, refuses an invalid
    plan without writing, and refuses a version older than the newest history snapshot.
"""
from __future__ import annotations

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

# fixture name → substring every violation line for it must contain
INVALID = {
    "invalid-duplicate-id": "duplicate id 'T1'",
    "invalid-unresolved-dep": "depends_on 'T99' does not resolve",
    "invalid-parallel-file-conflict": "parallel steps T1 and T2 both modify 'src/shared.py'",
    "invalid-missing-red-run": "red.run must be a non-empty command",
    "invalid-empty-verify": "verify must be a non-empty list",
    "invalid-unknown-touch": "touches 'ghost' which is not in context.components",
    "invalid-bad-version": "version: must be a positive integer",
    "invalid-bad-status": "status: 'shipped' is not one of draft|in_review|approved|rejected",
    "invalid-bad-review-status": "review.status 'maybe' is not one of pending|approved|deferred|edited|changed",
    "invalid-secret-aws": "secret: possible AWS access key",
    "invalid-secret-credential": "secret: possible hardcoded credential",
    "invalid-secret-key-named": "secret: key 'token' holds a credential-sized value",
    "invalid-secret-token-value": "secret: possible GitHub token",
    "invalid-home-path": "absolute home path '/home/alex/project/x.py'",
    "invalid-bad-path": "path '../outside/x.py' must be relative to the project root",
    "invalid-wrong-schema": "schema: expected 'magician.plan/1'",
    "invalid-destructive-verify": "verify holds a destructive command form 'rm -rf'",
    "invalid-step-wave-mismatch": "step T1: not listed in wave W2",
    "invalid-dependency-cycle": "depends_on: dependency cycle T1 -> T3 -> T1",
    "invalid-forward-dependency": "step T1: depends on T7, which runs in a later wave (W3)",
    "invalid-parallel-on-sequential": "step T3: a parallel step cannot depend on sequential step T4 of the same wave",
    "invalid-heading-forgery": "text: $.steps[0].intent has a line starting with '###', which would forge plan.md structure",
    "invalid-newline-in-title": "text: $.steps[0].title must be a single line",
    "invalid-control-char": "text: $.title holds a control character",
    "invalid-fence-in-diff": "text: $.steps[0].diff_sketch has a line starting with '```'",
    "invalid-bad-step-id": "steps[0]: needs an id of the form T<n>",
    "invalid-float-minutes": "step T1: effort.minutes must be a non-negative integer",
    "invalid-bad-history": "step T1: history[0] must be {v: int, changed: [field, …], summary?, diff?}",
    "invalid-bad-types": "step T1: depends_on entries must be step ids (strings)",
}
BAD_TYPES_LINES = ("research: must be a list of strings", "context.stack: must be a list of strings",
                   "context.blast[6]: must be {path: string, files: int, hits: int}",
                   "context.edges[13]: must be {from: id, to: id}", "step T2: field 'touches' must be a list")


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
        self.assertEqual(sorted(p.stem for p in FIX.glob("invalid-*.json")), sorted(INVALID))
        for name, needle in INVALID.items():
            with self.subTest(fixture=name):
                p = run("check", str(FIX / f"{name}.json"))
                self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                self.assertIn(needle, p.stdout)
                self.assertIn("violation(s)", p.stderr)
                self.assertTrue(all(line.strip() for line in p.stdout.splitlines()), "one line per violation")
        p = run("check", str(FIX / "invalid-bad-types.json"))
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
        for cmd in ("rm --recursive x", "find . -name '*.pyc' -delete", "curl x | sh", "terraform destroy",
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
                p = run(cmd, str(FIX / "invalid-unresolved-dep.json"))
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
        self.assertIn("'/events'", self.html)
        self.assertIn("'/state'", self.html)
        self.assertIn("Static — this page cannot reach the session; reply in chat", self.html)
        self.assertNotIn("Math.random", self.html, "no simulated Claude replies")
        self.assertIn("This page is static: the reason is copied as a chat line `plan: rejected — <reason>` for you to paste; nothing is archived from here.", self.html)
        self.assertIn('<span class="chip" id="tally" aria-live="polite">', self.html)
        self.assertIn("function nextPlayable", self.html, "Play skips deferred steps")
        self.assertIn('<dt><span class="kbd">?</span></dt><dd>This help</dd>', self.html)
        self.assertIn('<h2 aria-live="polite">', self.html)
        self.assertIn("function trap(e)", self.html, "dialogs trap focus")

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


class AllTests(unittest.TestCase):
    def test_all_writes_three_files_and_a_history_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "2026-11-01-feature"
            folder.mkdir()
            shutil.copy(VALID, folder / "plan.json")
            p = run("all", str(folder / "plan.json"), cwd=folder)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertEqual(p.stdout.splitlines(), ["plan.md", "plan.html", os.path.join("history", "plan.v1.json")])
            self.assertEqual((folder / "plan.md").read_bytes(), (FIX / "valid.md").read_bytes())
            self.assertEqual((folder / "plan.html").read_bytes(), (FIX / "valid.html").read_bytes())
            self.assertEqual((folder / "history" / "plan.v1.json").read_bytes(), VALID.read_bytes())
            self.assertEqual(sorted(x.name for x in folder.iterdir()), ["history", "plan.html", "plan.json", "plan.md"])
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
            shutil.copy(FIX / "invalid-unresolved-dep.json", folder / "plan.json")
            p = run("all", str(folder / "plan.json"), cwd=folder)
            self.assertEqual(p.returncode, 2)
            self.assertIn("nothing rendered", p.stderr)
            self.assertEqual([x.name for x in folder.iterdir()], ["plan.json"])


class CliTests(unittest.TestCase):
    def test_help_and_usage(self) -> None:
        p = run("--help")
        self.assertEqual(p.returncode, 0)
        for cmd in ("check", "md", "html", "diff", "all"):
            self.assertIn(f"plan-render {cmd} ", p.stdout)
        self.assertIn("--theme light|dark|auto", p.stdout)
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
