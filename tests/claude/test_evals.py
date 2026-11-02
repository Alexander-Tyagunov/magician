"""Static contract for the `evals/` behavioral suite (the `claude plugin eval --trust-plugin` gate).

Running the eval suite spends API budget and needs the network, so this gate does the part that
can and must run offline every time: it proves the suite is *well-formed and honest* before anyone
pays to run it. A grader that names a skill or agent the plugin does not ship is a silent false
pass — it can never fire — so this cross-checks every asserted skill/agent/tool against what the
plugin actually registers. The key sets below are the strict schema of `claude plugin eval`
(schema_version 1.1, Claude Code 2.1.3xx): an unknown key makes the runner refuse the case.

It also unit-tests the two offline helpers: `evals/flip.py` (the flip-aware gate behind
`scripts/gate.sh --evals`) and `evals/lens-ab/summarize.py` (the lens-model A/B summary), both
on fixture JSON, and dry-runs `evals/lens-ab/run.sh`.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))  # importable as tests.claude.test_evals
from _frontmatter import read_frontmatter


ROOT = Path(__file__).resolve().parents[2]
EVALS = ROOT / "evals"
SKILLS = ROOT / "skills"
AGENTS = ROOT / "agents"

# prompt.md frontmatter keys the runner accepts (top-level and execution keys).
PROMPT_KEYS = {"schema_version", "name", "description", "tags", "plugins", "runs", "expected_outcome",
               "model", "max_turns", "timeout_seconds", "allowed_tools", "disallowed_tools",
               "artifact_publish", "growthbook_overrides", "append_system_prompt", "env"}
# Keys every magician case sets, so a reader knows what it proves and what a pass looks like.
REQUIRED_PROMPT_KEYS = {"name", "description", "tags", "runs", "max_turns", "allowed_tools", "expected_outcome"}
CASE_YAML_KEYS = {"schema_version", "name", "description", "tags", "plugins", "runs", "expected_outcome",
                  "context", "execution", "graders"}
CONTEXT_KEYS = {"scaffold_script", "history_file", "add_dirs"}

# Grader types the runner supports: the fields each one requires, and every field it accepts.
GRADER_REQUIRED_FIELDS = {
    "regex": {"pattern"},
    "tool_used": {"tool"},
    "tool_order": {"before", "after"},
    "file_exists": {"path"},
    "llm": {"criteria"},       # in graders/*.md the rubric is the body
    "baseline": {"baseline_file", "criteria"},
}
_COMMON = {"type", "name", "weight", "arm"}
GRADER_ALLOWED_FIELDS = {
    "regex": _COMMON | {"target", "pattern", "flags", "match"},
    "tool_used": _COMMON | {"tool", "input_match", "min", "max"},
    "tool_order": _COMMON | {"before", "after"},
    "file_exists": _COMMON | {"path", "exists"},
    "llm": _COMMON | {"criteria", "focus"},
    "baseline": _COMMON | {"baseline_file", "criteria"},
}
BODY_FIELD = {"llm": "criteria", "baseline": "criteria", "regex": "pattern"}

# Tools an eval case may grant or a grader may assert. `Agent` is the subagent tool (`Task` is its
# older name); Monitor and the worktree tools are never available inside an eval run.
KNOWN_TOOLS = {
    "Read", "Write", "Edit", "NotebookEdit", "NotebookRead", "Bash", "Grep", "Glob",
    "Task", "Agent", "WebFetch", "WebSearch", "AskUserQuestion", "Skill", "Monitor", "Workflow",
    "TodoWrite",
}
WRITE_TOOLS = {"Write", "Edit", "Bash", "NotebookEdit"}

# Options of `claude plugin eval` (from `claude plugin eval --help`, 2.1.3xx).
EVAL_OPTIONS = {"--ablation", "--allow-real-servers", "--allow-tools", "--case", "-j", "--concurrency",
                "--disallow-tools", "--eval-dir", "--json", "--judge-model", "--keep-temp",
                "--max-cost-usd", "--mocks", "--model", "--no-publish", "--no-scaffold", "--output-dir",
                "--publish-report", "--report", "--runs", "--scaffold", "--tag", "--threshold",
                "--trust-plugin", "--verbose"}


def case_dirs() -> list[Path]:
    return sorted(d for d in EVALS.rglob("*")
                  if d.is_dir() and "results" not in d.relative_to(EVALS).parts
                  and ((d / "prompt.md").exists() or (d / "case.yaml").exists()))


def _list(raw) -> list[str]:
    if isinstance(raw, list):
        return [str(x) for x in raw]
    raw = str(raw or "").strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [t.strip().strip("'\"") for t in raw.split(",") if t.strip()]


def case_yaml(case: Path) -> dict:
    """case.yaml in this suite is written as JSON (valid YAML), so the stdlib can read it."""
    path = case / "case.yaml"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def case_fields(case: Path) -> dict:
    """The merged top-level fields, prompt.md frontmatter winning over case.yaml (as the runner does)."""
    merged = {k: v for k, v in case_yaml(case).items() if k not in ("graders", "context", "execution")}
    merged.update(case_yaml(case).get("execution", {}))
    if (case / "prompt.md").exists():
        fields, _ = read_frontmatter(case / "prompt.md")
        merged.update(fields)
    return merged


def graders_of(case: Path) -> list[tuple[str, dict]]:
    """[(label, fields)] for every grader: graders/*.md (name from the file, rubric or pattern from
    the body when the frontmatter lacks it) and the inline graders[] of case.yaml."""
    out = []
    for path in sorted((case / "graders").glob("*.md")):
        fields, body = read_frontmatter(path)
        fields = dict(fields)
        fields.setdefault("name", path.stem)
        key = BODY_FIELD.get(fields.get("type", ""))
        if key and key not in fields and body.strip():
            fields[key] = body.strip()
        out.append((path.name, fields))
    for g in case_yaml(case).get("graders", []):
        out.append(("case.yaml:" + str(g.get("name")), dict(g)))
    return out


def text_of_case(case: Path) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(case.rglob("*")) if p.is_file())


def _skill_names() -> set[str]:
    return {p.parent.name for p in SKILLS.glob("*/SKILL.md")}


def _agent_names() -> set[str]:
    return {p.stem for p in AGENTS.glob("*.md")}


def _tool_of(spec) -> str:
    return spec.get("tool") if isinstance(spec, dict) else str(spec)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


flip = _load("magician_eval_flip", EVALS / "flip.py")
summarize = _load("magician_lens_ab_summarize", EVALS / "lens-ab" / "summarize.py")


class EvalSuiteTests(unittest.TestCase):
    def test_suite_exists_and_is_discoverable(self) -> None:
        """The runner discovers every evals/**/prompt.md or case.yaml. Ten golden cases is the
        floor to start an eval set; the suite pairs positives with negative controls."""
        self.assertTrue(EVALS.is_dir(), "no evals/ directory")
        self.assertGreaterEqual(len(case_dirs()), 10, "eval suite under the 10-golden-case floor")
        negatives = [c for c in case_dirs() if "negative-control" in _list(case_fields(c).get("tags"))]
        self.assertGreaterEqual(len(negatives), 2, "the suite needs should-not-fire controls")

    def test_case_names_match_folders_and_are_unique(self) -> None:
        names = []
        for case in case_dirs():
            with self.subTest(case=case.name):
                fields = case_fields(case)
                self.assertEqual(fields.get("name"), case.name, "case name must match its folder")
                if (case / "case.yaml").exists():
                    self.assertEqual(case_yaml(case).get("name"), case.name)
                names.append(fields.get("name"))
        self.assertEqual(len(names), len(set(names)), "duplicate case names")

    def test_every_case_has_a_prompt_and_graders(self) -> None:
        for case in case_dirs():
            with self.subTest(case=case.name):
                fields, body = read_frontmatter(case / "prompt.md") if (case / "prompt.md").exists() else ({}, "")
                prompt = body.strip() or case_yaml(case).get("execution", {}).get("prompt", "")
                self.assertTrue(prompt.strip(), "case has no prompt")
                self.assertTrue(graders_of(case), "case has no graders — nothing is asserted")

    def test_prompt_frontmatter_has_the_required_and_only_known_keys(self) -> None:
        for case in case_dirs():
            with self.subTest(case=case.name):
                if (case / "prompt.md").exists():
                    fields, _ = read_frontmatter(case / "prompt.md")
                    unknown = set(fields) - PROMPT_KEYS
                    self.assertFalse(unknown, f"prompt.md keys the runner refuses: {unknown}")
                merged = case_fields(case)
                missing = REQUIRED_PROMPT_KEYS - set(merged)
                self.assertFalse(missing, f"case lacks {missing}")
                self.assertGreaterEqual(int(merged["runs"]), 2, "run every task more than once")
                self.assertLessEqual(int(merged["runs"]), 50)
                self.assertTrue(str(merged["expected_outcome"]).strip())
                self._assert_tool_list(case.name, merged["allowed_tools"])

    def _assert_tool_list(self, case: str, raw) -> None:
        for tok in _list(raw):
            tool = re.match(r"[A-Za-z_]+", tok)
            with self.subTest(case=case, tool=tok):
                self.assertTrue(tool, f"{case}: bad allowed_tools entry {tok!r}")
                if tool.group(0) == "mcp":
                    continue
                self.assertIn(tool.group(0), KNOWN_TOOLS, f"{case}: allowed_tools names unknown tool {tok!r}")

    def test_case_yaml_is_json_with_known_keys_and_a_real_scaffold(self) -> None:
        for case in case_dirs():
            path = case / "case.yaml"
            if not path.exists():
                continue
            with self.subTest(case=case.name):
                try:
                    doc = json.loads(path.read_text(encoding="utf-8"))
                except ValueError as exc:
                    self.fail(f"case.yaml is not JSON (this suite writes it as JSON): {exc}")
                self.assertEqual(doc.get("schema_version"), "1.1")
                self.assertFalse(set(doc) - CASE_YAML_KEYS, f"unknown case.yaml keys {set(doc) - CASE_YAML_KEYS}")
                context = doc.get("context", {})
                self.assertFalse(set(context) - CONTEXT_KEYS)
                script = context.get("scaffold_script")
                if script:
                    target = (case / script).resolve()
                    self.assertTrue(target.is_file(), "scaffold_script does not exist")
                    self.assertTrue(str(target).startswith(str(case.resolve()) + os.sep),
                                    "scaffold_script must stay inside the case folder")
                    syntax = subprocess.run(["bash", "-n", str(target)], capture_output=True, text=True)
                    self.assertEqual(syntax.returncode, 0, syntax.stderr)

    def test_scaffolds_stage_their_fixture(self) -> None:
        """Run every scaffold for real in a temp folder, the way the runner does (bash <script>,
        cwd = the run folder), and check it exits 0 and leaves files behind."""
        for case in case_dirs():
            script = case_yaml(case).get("context", {}).get("scaffold_script")
            if not script:
                continue
            with self.subTest(case=case.name), tempfile.TemporaryDirectory() as tmp:
                env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": tmp, "TMPDIR": tmp,
                       "TERM": "dumb", "GIT_CONFIG_NOSYSTEM": "1"}
                res = subprocess.run(["bash", str(case / script)], cwd=tmp, env=env,
                                     capture_output=True, text=True, timeout=60)
                self.assertEqual(res.returncode, 0, res.stderr)
                staged = [p for p in Path(tmp).rglob("*") if p.is_file() and ".git" not in p.parts]
                self.assertTrue(staged, "scaffold staged no file")

    def test_every_grader_declares_a_known_type_with_its_required_fields(self) -> None:
        for case in case_dirs():
            names = []
            for label, fields in graders_of(case):
                with self.subTest(case=case.name, grader=label):
                    gtype = fields.get("type")
                    self.assertIn(gtype, GRADER_REQUIRED_FIELDS, f"unknown grader type {gtype!r}")
                    missing = GRADER_REQUIRED_FIELDS[gtype] - set(fields)
                    self.assertFalse(missing, f"{gtype} grader missing fields {missing}")
                    unknown = set(fields) - GRADER_ALLOWED_FIELDS[gtype]
                    self.assertFalse(unknown, f"{gtype} grader has keys the runner refuses: {unknown}")
                    if gtype == "llm":
                        self.assertTrue(str(fields["criteria"]).strip(), "llm grader has an empty rubric")
                    if "arm" in fields:
                        self.assertIn(fields["arm"], ("with-only", "both"))
                    if "match" in fields:
                        self.assertRegex(str(fields["match"]), r"^(?:contains|not_contains|count:\d+)$")
                    names.append(fields.get("name"))
            self.assertEqual(len(names), len(set(names)), f"{case.name}: duplicate grader names")

    def test_every_case_has_an_outcome_grader(self) -> None:
        """Grade outcomes, not only trajectories: a tool_used grader alone never shows the work was
        right (and a `tool_used: Skill` grader is unscored under ablation)."""
        for case in case_dirs():
            with self.subTest(case=case.name):
                types = {f.get("type") for _, f in graders_of(case)}
                self.assertTrue(types - {"tool_used", "tool_order"}, "case has only trajectory graders")

    def test_regex_and_input_match_patterns_compile(self) -> None:
        for case in case_dirs():
            for label, fields in graders_of(case):
                patterns = [fields.get("pattern"), fields.get("input_match")]
                for side in ("before", "after"):
                    if isinstance(fields.get(side), dict):
                        patterns.append(fields[side].get("input_match"))
                for pat in filter(None, patterns):
                    with self.subTest(case=case.name, grader=label, pattern=pat):
                        try:
                            re.compile(pat)
                        except re.error as exc:
                            self.fail(f"{label}: not a valid regex: {exc}")

    def test_tool_graders_name_real_tools_that_the_case_grants(self) -> None:
        """Tools follow graders: a grader that needs a call of X only passes if the case grants X."""
        for case in case_dirs():
            granted = {re.match(r"[A-Za-z_]+", t).group(0) for t in _list(case_fields(case).get("allowed_tools"))}
            for label, fields in graders_of(case):
                gtype = fields.get("type")
                tools = []
                if gtype == "tool_used":
                    tools = [fields["tool"]]
                elif gtype == "tool_order":
                    tools = [_tool_of(fields["before"]), _tool_of(fields["after"])]
                for tool in tools:
                    with self.subTest(case=case.name, grader=label, tool=tool):
                        self.assertIn(tool, KNOWN_TOOLS, f"grader names unknown tool {tool!r}")
                        self.assertNotIn(tool, {"Monitor", "Task"}, "Monitor never runs in an eval; Task is now Agent")
                        must_be_granted = gtype == "tool_order" or int(fields.get("min", 1)) >= 1
                        if must_be_granted or tool == "Agent":
                            self.assertIn(tool, granted, f"grader needs {tool} but allowed_tools lacks it")
                if gtype == "file_exists" and str(fields.get("exists", True)).lower() != "false":
                    with self.subTest(case=case.name, grader=label):
                        self.assertTrue(granted & WRITE_TOOLS, "file grader but no tool can create a file")

    def test_absence_graders_are_scored_in_both_arms(self) -> None:
        """A must-NOT-call grader sets min 0, max 0 and arm both; without arm, a Skill grader is a
        display-only indicator under --ablation with-without and never fails the case."""
        for case in case_dirs():
            for label, fields in graders_of(case):
                if fields.get("type") != "tool_used" or str(fields.get("max", "")) != "0":
                    continue
                with self.subTest(case=case.name, grader=label):
                    self.assertEqual(str(fields.get("min")), "0")
                    self.assertEqual(fields.get("arm"), "both")

    def test_negative_controls_assert_an_absence(self) -> None:
        for case in case_dirs():
            if "negative-control" not in _list(case_fields(case).get("tags")):
                continue
            with self.subTest(case=case.name):
                absent = [f for _, f in graders_of(case)
                          if str(f.get("max", "")) == "0" or f.get("match") == "not_contains"
                          or str(f.get("exists", "")).lower() == "false"]
                self.assertTrue(absent, "a negative control must assert that something did NOT happen")

    def test_asserted_skills_and_agents_actually_exist(self) -> None:
        """The load-bearing check: an eval that asserts a Skill/Agent by name is only meaningful if
        that skill/agent ships. A typo'd name makes the grader unfireable — a silent false pass."""
        skills = _skill_names()
        agents = _agent_names()
        for case in case_dirs():
            for label, fields in graders_of(case):
                if fields.get("type") != "tool_used":
                    continue
                names = self._names_in_alternation(fields.get("input_match", ""))
                tool = fields.get("tool")
                for name in names:
                    with self.subTest(case=case.name, grader=label, name=name):
                        if tool == "Skill":
                            self.assertIn(name, skills, f"eval asserts missing skill {name!r}")
                        elif tool in ("Task", "Agent"):
                            self.assertIn(name, agents, f"eval asserts missing agent {name!r}")

    @staticmethod
    def _names_in_alternation(input_match: str) -> list[str]:
        """Pull the concrete identifier(s) an input_match pins, e.g.
        '...:"(?:divine|scrutinize)"' -> ['divine', 'scrutinize']. Returns [] if it can't tell."""
        tail = re.search(r':\s*"([^"]*)"\s*$', input_match) or re.search(r'"([^"]*)"\s*$', input_match)
        if not tail:
            return []
        segment = tail.group(1)
        segment = re.sub(r"\(\?:\[\\?w-\]\+:\)\?", "", segment)
        alt = re.search(r"\(\?:([\w|-]+)\)|([\w-]+)$", segment)
        if not alt:
            return []
        body = alt.group(1) or alt.group(2) or ""
        return [p for p in body.split("|") if re.fullmatch(r"[\w-]+", p)]

    def test_no_case_pastes_recorded_output(self) -> None:
        """Never paste failure content from an earlier run into a case: a heuristic that no case file
        points into a results folder or quotes a run artifact."""
        for case in case_dirs():
            with self.subTest(case=case.name):
                text = text_of_case(case)
                self.assertNotRegex(text, r"(?:^|[\s`'\"(/])results/", "case references a results/ path")
                self.assertNotRegex(text, r"aggregate-result\.json|trace_path|\.gate-evals")

    def test_no_absolute_or_home_paths_in_prompts(self) -> None:
        """Cases run in a sandbox cwd: a prompt or grader path outside it can never resolve."""
        for case in case_dirs():
            for label, fields in graders_of(case):
                target = fields.get("target") or fields.get("focus")
                path = target.get("path") if isinstance(target, dict) else fields.get("path")
                if path:
                    with self.subTest(case=case.name, grader=label):
                        self.assertFalse(str(path).startswith(("/", "~")), "grader path must be relative")
                        self.assertNotIn("..", Path(str(path)).parts)

    def test_expected_fail_cases_are_documented(self) -> None:
        readme = (EVALS / "README.md").read_text(encoding="utf-8")
        for case in case_dirs():
            if "expected-fail" in _list(case_fields(case).get("tags")):
                with self.subTest(case=case.name):
                    self.assertIn(case.name, readme, "an expected-fail case must say in evals/README.md why")

    def test_every_case_is_listed_in_the_readme(self) -> None:
        readme = (EVALS / "README.md").read_text(encoding="utf-8")
        for case in case_dirs():
            with self.subTest(case=case.name):
                self.assertIn(f"`{case.name}`", readme)

    def test_lens_ab_cases_have_lens_named_graders(self) -> None:
        lens_cases = [c for c in case_dirs() if "lens-ab" in _list(case_fields(c).get("tags"))]
        self.assertGreaterEqual(len(lens_cases), 2)
        for case in lens_cases:
            with self.subTest(case=case.name):
                lenses = {summarize.lens_of(str(f.get("name"))) for _, f in graders_of(case)}
                self.assertTrue(lenses & {"simplifier", "verifier"} or lenses & {"reviewer"},
                                "a lens-ab case needs graders named after a lens")
        all_lenses = {summarize.lens_of(str(f.get("name"))) for c in lens_cases for _, f in graders_of(c)}
        self.assertTrue({"simplifier", "verifier"} <= all_lenses, "the A/B needs simplifier and verifier graders")

    def test_baseline_file_is_tracked_and_well_formed(self) -> None:
        last = EVALS / "results" / "last.json"
        doc = json.loads(last.read_text(encoding="utf-8"))
        self.assertEqual(doc.get("schema"), 1)
        self.assertIsInstance(doc.get("cases"), dict)
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("!evals/results/last.json", ignore)

    def test_gate_and_lens_ab_use_only_documented_eval_flags(self) -> None:
        for path in (ROOT / "scripts" / "gate.sh", EVALS / "lens-ab" / "run.sh"):
            text = path.read_text(encoding="utf-8")
            block = "\n".join(re.findall(r"(?:eval_cmd|cmd)(?:\+?=)\(([^)]*)\)", text))
            flags = set(re.findall(r"(?<![\w-])(--[a-z][a-z-]+)", block))
            with self.subTest(script=path.name):
                self.assertTrue(flags, "no eval command found")
                self.assertFalse(flags - EVAL_OPTIONS, f"undocumented flags {flags - EVAL_OPTIONS}")
        gate = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
        for flag in ("--trust-plugin", "--json", "--threshold", "--no-publish", "--max-cost-usd",
                     "--ablation with-without", "MAGICIAN_EVAL_MAX_COST:-20", "evals/flip.py",
                     "--update-baseline", "MAGICIAN_EVAL_UPDATE_BASELINE"):
            with self.subTest(flag=flag):
                self.assertIn(flag, gate)


# ---- flip-aware gate (evals/flip.py) -------------------------------------------------------------

def _shape_a(cases: dict[str, list[float]]) -> dict:
    """The --json shape Claude Code writes: cases[].name + runs[].score (1.0 = every grader passed)."""
    return {"cases": [{"name": n, "score": sum(s) / len(s), "pass_rate": sum(1 for x in s if x >= 1) / len(s),
                       "runs": [{"score": x, "graders": [], "error": None} for x in s]}
                      for n, s in cases.items()]}


def _shape_b(cases: dict[str, float]) -> dict:
    return {"results": [{"case": n, "score": s} for n, s in cases.items()]}


class FlipParserTests(unittest.TestCase):
    def test_parses_cases_and_runs_shape(self) -> None:
        got = flip.parse_results(_shape_a({"a": [1.0, 1.0, 1.0], "b": [1.0, 0.5, 1.0]}))
        self.assertEqual(got["a"]["passed"], 3)
        self.assertTrue(flip.all_passed(got["a"]))
        self.assertEqual((got["b"]["passed"], got["b"]["runs"]), (2, 3))
        self.assertFalse(flip.all_passed(got["b"]))

    def test_runs_with_passed_flags_and_errors(self) -> None:
        doc = {"cases": [{"name": "c", "runs": [{"passed": True}, {"passed": False}]},
                         {"name": "d", "runs": [{"score": 1.0, "error": "timed out"}]}]}
        got = flip.parse_results(doc)
        self.assertEqual(got["c"]["passed"], 1)
        self.assertEqual(got["d"]["passed"], 0, "a run with an error never counts as passed")

    def test_parses_results_and_score_shape(self) -> None:
        got = flip.parse_results(_shape_b({"a": 1.0, "b": 0.67}))
        self.assertTrue(flip.all_passed(got["a"]))
        self.assertFalse(flip.all_passed(got["b"]))
        self.assertAlmostEqual(got["b"]["score"], 0.67)

    def test_rejects_an_unknown_shape(self) -> None:
        with self.assertRaises(ValueError):
            flip.parse_results({"summary": {}})

    def test_flip_new_improved_and_steady(self) -> None:
        base = flip.parse_results(_shape_a({"flips": [1, 1, 1], "better": [1, 0, 0], "same": [1, 1, 1]}))
        cur = flip.parse_results(_shape_a({"flips": [1, 0.5, 1], "better": [1, 1, 0], "same": [1, 1, 1],
                                           "fresh": [0, 1, 1]}))
        rep = flip.compare(base, cur, {}, threshold=0.5)
        self.assertEqual(rep["flipped"], ["flips"])
        self.assertEqual(rep["improved"], ["better"])
        self.assertEqual(rep["new"], ["fresh"])
        self.assertEqual(rep["steady"], ["same"])
        self.assertTrue(rep["failed"], "a flip fails even when every score clears the threshold")

    def test_flip_fails_even_when_the_aggregate_is_high(self) -> None:
        names = {"c%d" % i: [1, 1, 1] for i in range(12)}
        base = flip.parse_results(_shape_a(names))
        names["c0"] = [1, 1, 0.9]
        cur = flip.parse_results(_shape_a(names))
        rep = flip.compare(base, cur, {}, threshold=0.8)
        self.assertEqual(rep["flipped"], ["c0"])
        self.assertEqual(rep["below_threshold"], [])
        self.assertTrue(rep["failed"])

    def test_new_and_improved_cases_never_fail(self) -> None:
        base = flip.parse_results(_shape_a({"a": [1, 0, 0]}))
        cur = flip.parse_results(_shape_a({"a": [1, 1, 0.9], "b": [1, 1, 1]}))
        rep = flip.compare(base, cur, {}, threshold=0.8)
        self.assertFalse(rep["failed"], rep["reasons"])

    def test_expected_fail_is_excused_until_it_first_passes(self) -> None:
        tags = {"inline": {"routing", "expected-fail"}}
        cur = flip.parse_results(_shape_a({"inline": [0, 0, 0]}))
        rep = flip.compare({}, cur, tags, threshold=0.8)
        self.assertEqual(rep["expected_fail"], ["inline"])
        self.assertFalse(rep["failed"], "an expected-fail case below threshold must not fail the tier")
        now_passing = flip.parse_results(_shape_a({"inline": [1, 1, 1]}))
        rep = flip.compare({}, now_passing, tags, threshold=0.8)
        self.assertEqual(rep["expected_fail_now_passing"], ["inline"])
        # Once the baseline records it passing, a later failure is a flip like any other.
        rep = flip.compare(now_passing, cur, tags, threshold=0.8)
        self.assertEqual(rep["flipped"], ["inline"])
        self.assertTrue(rep["failed"])

    def test_case_tags_read_prompt_and_case_yaml(self) -> None:
        tags = flip.case_tags(EVALS)
        self.assertIn("expected-fail", tags["small-diff-stays-inline"])
        self.assertIn("fold-first", tags["large-plan-fans-out"])
        self.assertNotIn("expected-fail", tags["large-plan-fans-out"])

    def _main(self, doc, baseline: dict | None, exit_code: int, *extra: str) -> tuple[int, str, Path]:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        res, last = tmp / "results.json", tmp / "last.json"
        res.write_text(json.dumps(doc))
        if baseline is not None:
            last.write_text(json.dumps(flip.baseline_doc(baseline)))
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = flip.main(["compare", "--results", str(res), "--baseline", str(last), "--evals-dir",
                            str(EVALS), "--threshold", "0.8", "--exit-code", str(exit_code), *extra])
        return rc, buf.getvalue(), last

    def test_main_prints_flipped_and_fails(self) -> None:
        base = flip.parse_results(_shape_a({"tdd-red-before-green": [1, 1, 1]}))
        rc, out, _ = self._main(_shape_a({"tdd-red-before-green": [1, 1, 0.5]}), base, 1)
        self.assertEqual(rc, 1)
        self.assertIn("flipped: tdd-red-before-green", out)

    def test_main_accepts_exit_1_explained_by_expected_fail(self) -> None:
        rc, out, _ = self._main(_shape_a({"small-diff-stays-inline": [0, 0, 0.5], "ste-spec-writing": [1, 1, 1]}), {}, 1)
        self.assertEqual(rc, 0, out)
        self.assertIn("expected-fail: small-diff-stays-inline", out)
        self.assertIn("new: ste-spec-writing", out)

    def test_main_fails_an_unexplained_exit_1_and_partial_runs(self) -> None:
        rc, out, _ = self._main(_shape_a({"ste-spec-writing": [1, 1, 1]}), {}, 1)
        self.assertEqual(rc, 1, out)
        rc, out, _ = self._main(_shape_a({"ste-spec-writing": [1, 1, 1]}), {}, 2)
        self.assertEqual(rc, 1, out)

    def test_main_fails_on_load_errors_and_api_error_runs(self) -> None:
        doc = _shape_a({"ste-spec-writing": [1, 1, 1]})
        doc["errors"] = [{"file": "evals/x/prompt.md", "error": "unknown frontmatter key"}]
        rc, out, _ = self._main(doc, {}, 1)
        self.assertEqual(rc, 1)
        self.assertIn("load error", out)
        doc = _shape_a({"ste-spec-writing": [1, 1, 1]})
        doc["cases"][0]["runs"][0]["ended_on_api_error"] = True
        rc, out, _ = self._main(doc, {}, 1)
        self.assertEqual(rc, 1)

    def test_main_fails_when_results_are_missing(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        with redirect_stdout(io.StringIO()):
            rc = flip.main(["compare", "--results", str(tmp / "none.json"), "--baseline", str(tmp / "l.json"),
                            "--evals-dir", str(EVALS)])
        self.assertEqual(rc, 1)

    def test_update_baseline_rewrites_last_json(self) -> None:
        rc, out, last = self._main(_shape_b({"ste-spec-writing": 1.0}), None, 0, "--update-baseline")
        self.assertEqual(rc, 0, out)
        doc = json.loads(last.read_text())
        self.assertEqual(doc["schema"], 1)
        self.assertIn("ste-spec-writing", doc["cases"])
        self.assertIn("baseline updated", out)

    def test_update_baseline_from_the_environment(self) -> None:
        old = os.environ.get("MAGICIAN_EVAL_UPDATE_BASELINE")
        os.environ["MAGICIAN_EVAL_UPDATE_BASELINE"] = "1"
        try:
            rc, out, last = self._main(_shape_b({"ste-spec-writing": 1.0}), None, 0)
        finally:
            if old is None:
                os.environ.pop("MAGICIAN_EVAL_UPDATE_BASELINE")
            else:
                os.environ["MAGICIAN_EVAL_UPDATE_BASELINE"] = old
        self.assertTrue(last.exists(), out)


    def test_update_baseline_refuses_a_failed_run(self) -> None:
        base = flip.parse_results(_shape_a({"tdd-red-before-green": [1, 1, 1]}))
        for doc, why in ((_shape_a({"tdd-red-before-green": [1, 1, 0.5]}), "flip"),
                         (_shape_a({"tdd-red-before-green": [0.5, 0.5, 0.5]}), "below threshold")):
            with self.subTest(why=why):
                rc, out, last = self._main(doc, base, 1, "--update-baseline")
                self.assertEqual(rc, 1, out)
                self.assertIn("baseline NOT updated", out)
                self.assertEqual(flip.read_baseline(last), base, "the baseline must be left as it was")

    def test_force_baseline_writes_a_failed_run(self) -> None:
        base = flip.parse_results(_shape_a({"tdd-red-before-green": [1, 1, 1]}))
        rc, out, last = self._main(_shape_a({"tdd-red-before-green": [1, 1, 0.5]}), base, 1,
                                   "--update-baseline", "--force-baseline")
        self.assertEqual(rc, 1, out)
        self.assertIn("forced from a failed run", out)
        self.assertEqual(flip.read_baseline(last)["tdd-red-before-green"]["passed"], 2)

    def test_missing_baseline_case_fails_an_unfiltered_run(self) -> None:
        base = flip.parse_results(_shape_a({"tdd-red-before-green": [1, 1, 1], "ste-spec-writing": [1, 1, 1]}))
        rc, out, last = self._main(_shape_a({"ste-spec-writing": [1, 1, 1]}), base, 0, "--update-baseline")
        self.assertEqual(rc, 1, out)
        self.assertIn("missing: tdd-red-before-green", out)
        self.assertIn("baseline NOT updated", out)

    def test_missing_baseline_case_is_only_reported_on_a_tag_filtered_run(self) -> None:
        base = flip.parse_results(_shape_a({"tdd-red-before-green": [1, 1, 1], "ste-spec-writing": [1, 1, 1]}))
        rc, out, last = self._main(_shape_a({"ste-spec-writing": [1, 1, 1]}), base, 0,
                                   "--tag-filtered", "--update-baseline")
        self.assertEqual(rc, 0, out)
        self.assertIn("not run this time (tag-filtered run): tdd-red-before-green", out)
        self.assertEqual(set(flip.read_baseline(last)), {"tdd-red-before-green", "ste-spec-writing"},
                         "a filtered run merges into the baseline")

    def test_tag_filter_comes_from_the_gate_environment(self) -> None:
        base = flip.parse_results(_shape_a({"tdd-red-before-green": [1, 1, 1], "ste-spec-writing": [1, 1, 1]}))
        old = os.environ.get("MAGICIAN_EVAL_TAG_FILTERED")
        os.environ["MAGICIAN_EVAL_TAG_FILTERED"] = "1"
        try:
            rc, out, _ = self._main(_shape_a({"ste-spec-writing": [1, 1, 1]}), base, 0)
        finally:
            if old is None:
                os.environ.pop("MAGICIAN_EVAL_TAG_FILTERED")
            else:
                os.environ["MAGICIAN_EVAL_TAG_FILTERED"] = old
        self.assertEqual(rc, 0, out)

    def test_gate_passes_tag_and_sets_the_filter_env(self) -> None:
        gate = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
        self.assertIn("--tag) ", gate)
        self.assertIn("eval_cmd+=(--tag", gate)
        self.assertIn("MAGICIAN_EVAL_TAG_FILTERED=1", gate)

# ---- lens-model A/B (evals/lens-ab) --------------------------------------------------------------

def _lens_report(passes: dict[str, list[bool]], cost: float = 0.25) -> dict:
    runs = []
    n = len(next(iter(passes.values())))
    for i in range(n):
        runs.append({"score": 1.0, "cost_usd": cost, "error": None,
                     "graders": [{"name": g, "passed": v[i], "scored": True, "weight": 1} for g, v in passes.items()]})
    return {"cases": [{"name": "review-uses-tags-and-count-line", "score": 1.0, "runs": runs}]}


class LensSummaryTests(unittest.TestCase):
    def test_recall_per_lens_per_model(self) -> None:
        reports = {
            "haiku": _lens_report({"simplifier-finds-needless-factory": [True, False, True],
                                   "verifier-finds-assertionless-test": [True, True, True],
                                   "count-line": [True, True, True]}),
            "sonnet": _lens_report({"simplifier-finds-needless-factory": [True, True, True],
                                    "verifier-finds-assertionless-test": [True, True, False],
                                    "count-line": [True, True, True]}, cost=1.0),
        }
        s = summarize.summarize(reports)
        self.assertEqual(s["lenses"]["simplifier"]["haiku"], [2, 3])
        self.assertEqual(s["lenses"]["simplifier"]["sonnet"], [3, 3])
        self.assertEqual(s["lenses"]["verifier"]["sonnet"], [2, 3])
        self.assertEqual(s["lenses"]["other"]["haiku"], [3, 3])
        self.assertAlmostEqual(s["cost"]["sonnet"], 3.0)
        text = summarize.render(s)
        self.assertIn("simplifier", text)
        self.assertIn("2/3 (67%)", text)
        self.assertIn("simplifier: haiku minus sonnet = -33 points", text)

    def test_errored_and_unscored_runs_are_not_misses(self) -> None:
        doc = _lens_report({"verifier-x": [True, True]})
        doc["cases"][0]["runs"].append({"score": 0, "cost_usd": 0, "error": "run could not start", "graders": []})
        doc["cases"][0]["runs"][0]["graders"].append({"name": "reviewer-y", "passed": False, "scored": False})
        s = summarize.summarize({"haiku": doc})
        self.assertEqual(s["errored"]["haiku"], 1)
        self.assertEqual(s["lenses"]["verifier"]["haiku"], [2, 2])
        self.assertNotIn("reviewer", s["lenses"])

    def test_main_reads_report_files_named_by_model(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        (tmp / "haiku.json").write_text(json.dumps(_lens_report({"simplifier-a": [True]})))
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = summarize.main([str(tmp / "haiku.json")])
        self.assertEqual(rc, 0)
        self.assertIn("haiku", buf.getvalue())

    def test_run_sh_is_bash_and_dry_runs_both_models(self) -> None:
        script = EVALS / "lens-ab" / "run.sh"
        self.assertTrue(os.access(script, os.X_OK), "run.sh must be executable")
        self.assertEqual(subprocess.run(["bash", "-n", str(script)]).returncode, 0)
        with tempfile.TemporaryDirectory() as tmp:
            res = subprocess.run(["bash", str(script), "--dry-run", "--out", tmp], capture_output=True,
                                 text=True, timeout=120, env={**os.environ, "TMPDIR": tmp})
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("on haiku", res.stdout)
            self.assertIn("on sonnet", res.stdout)
            self.assertIn("--tag lens-ab", res.stdout.replace("  ", " "))
            self.assertNotIn("results/", res.stdout.replace(tmp, ""))


if __name__ == "__main__":
    unittest.main()
