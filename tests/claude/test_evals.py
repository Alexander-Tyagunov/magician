"""Static contract for the `evals/` behavioral suite (the `claude plugin eval` gate).

Running the eval suite spends API budget and needs the network, so this gate does the part that
can and must run offline every time: it proves the suite is *well-formed and honest* before anyone
pays to run it. A grader that names a skill or agent the plugin does not ship is a silent false
pass — it can never fire — so this cross-checks every asserted skill/agent/tool against what the
plugin actually registers. (Schema per code.claude.com/docs/en/plugin-evals, schema_version 1.1.)
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

from _frontmatter import read_frontmatter


ROOT = Path(__file__).resolve().parents[2]
EVALS = ROOT / "evals"
SKILLS = ROOT / "skills"
AGENTS = ROOT / "agents"

# Grader types the runner supports, with the fields each one requires to be meaningful.
GRADER_REQUIRED_FIELDS = {
    "regex": {"pattern"},
    "tool_used": {"tool"},
    "tool_order": {"before", "after"},
    "file_exists": {"path"},
    "llm": set(),       # rubric lives in the body
    "baseline": {"baseline_file"},
}

# Tools an eval grader may assert were used.
KNOWN_TOOLS = {
    "Read", "Write", "Edit", "NotebookEdit", "Bash", "Grep", "Glob",
    "Task", "WebFetch", "WebSearch", "AskUserQuestion", "Skill", "Monitor", "Workflow",
}


def case_dirs() -> list[Path]:
    return sorted(d for d in EVALS.glob("*")
                  if d.is_dir() and ((d / "prompt.md").exists() or (d / "case.yaml").exists()))


def graders_of(case: Path) -> list[Path]:
    return sorted((case / "graders").glob("*.md"))


def _skill_names() -> set[str]:
    return {p.parent.name for p in SKILLS.glob("*/SKILL.md")}


def _agent_names() -> set[str]:
    return {p.stem for p in AGENTS.glob("*.md")}


class EvalSuiteTests(unittest.TestCase):
    def test_suite_exists_and_is_discoverable(self) -> None:
        """The runner auto-discovers evals/<case>/; there must be cases to discover. The behavioral
        tier gates what is *reliably* observable in the `claude plugin eval` sandbox — skill
        invocation (sentinel, divine) and hook enforcement (destructive-command block). Agent
        dispatchability is gated structurally in test_agents.py (frontmatter, least-privilege, and
        the skill→agent wiring), because model-discretionary Task-subagent spawning is not
        reproducible enough to hang a green gate on."""
        self.assertTrue(EVALS.is_dir(), "no evals/ directory")
        self.assertGreaterEqual(len(case_dirs()), 3, "eval suite too thin to gate behavior")

    def test_every_case_has_a_prompt_and_graders(self) -> None:
        for case in case_dirs():
            with self.subTest(case=case.name):
                self.assertTrue((case / "prompt.md").exists() or (case / "case.yaml").exists(),
                                "case has neither prompt.md nor case.yaml")
                self.assertTrue(graders_of(case), "case has no graders/ — nothing is asserted")

    def test_prompt_frontmatter_is_well_formed(self) -> None:
        for case in case_dirs():
            prompt = case / "prompt.md"
            if not prompt.exists():
                continue
            with self.subTest(case=case.name):
                fields, body = read_frontmatter(prompt)
                self.assertTrue(body.strip(), "empty prompt body")
                if "allowed_tools" in fields:
                    self._assert_tool_list(case.name, fields["allowed_tools"])

    def _assert_tool_list(self, case: str, raw: str) -> None:
        for tok in re.findall(r"[A-Za-z_]+", raw):
            if tok in {"mcp"}:
                continue
            with self.subTest(case=case, tool=tok):
                self.assertIn(tok, KNOWN_TOOLS, f"{case}: allowed_tools names unknown tool {tok!r}")

    def test_every_grader_declares_a_known_type_with_its_required_fields(self) -> None:
        for case in case_dirs():
            for grader in graders_of(case):
                fields, body = read_frontmatter(grader)
                with self.subTest(case=case.name, grader=grader.name):
                    gtype = fields.get("type")
                    self.assertIn(gtype, GRADER_REQUIRED_FIELDS, f"unknown grader type {gtype!r}")
                    missing = GRADER_REQUIRED_FIELDS[gtype] - set(fields)
                    self.assertFalse(missing, f"{gtype} grader missing fields {missing}")
                    if gtype == "llm":
                        self.assertTrue(body.strip(), "llm grader has an empty rubric body")

    def test_regex_and_input_match_patterns_compile(self) -> None:
        for case in case_dirs():
            for grader in graders_of(case):
                fields, _ = read_frontmatter(grader)
                for key in ("pattern", "input_match"):
                    if key not in fields:
                        continue
                    with self.subTest(case=case.name, grader=grader.name, key=key):
                        try:
                            re.compile(fields[key])
                        except re.error as exc:
                            self.fail(f"{grader.name}: {key} is not a valid regex: {exc}")

    def test_tool_used_graders_name_real_tools(self) -> None:
        for case in case_dirs():
            for grader in graders_of(case):
                fields, _ = read_frontmatter(grader)
                if fields.get("type") != "tool_used":
                    continue
                with self.subTest(case=case.name, grader=grader.name):
                    self.assertIn(fields["tool"], KNOWN_TOOLS,
                                  f"tool_used grader names unknown tool {fields['tool']!r}")

    def test_asserted_skills_and_agents_actually_exist(self) -> None:
        """The load-bearing check: an eval that asserts a Skill/Agent by name is only meaningful if
        that skill/agent ships. A typo'd name makes the grader unfireable — a silent false pass."""
        skills = _skill_names()
        agents = _agent_names()
        for case in case_dirs():
            for grader in graders_of(case):
                fields, _ = read_frontmatter(grader)
                if fields.get("type") != "tool_used":
                    continue
                match = fields.get("input_match", "")
                tool = fields.get("tool")
                names = self._names_in_alternation(match)
                if not names:
                    continue
                if tool == "Skill":
                    for name in names:
                        with self.subTest(case=case.name, skill=name):
                            self.assertIn(name, skills, f"eval asserts missing skill {name!r}")
                elif tool == "Task":
                    for name in names:
                        with self.subTest(case=case.name, agent=name):
                            self.assertIn(name, agents, f"eval asserts missing agent {name!r}")

    @staticmethod
    def _names_in_alternation(input_match: str) -> list[str]:
        """Pull the concrete identifier(s) an input_match pins, e.g.
        '...:"(?:divine|scrutinize)"' -> ['divine', 'scrutinize']. Returns [] if it can't tell."""
        # the target name sits in the final quoted group, after the optional `(?:...:)?` namespace
        tail = re.search(r':\s*"([^"]*)"\s*$', input_match) or re.search(r'"([^"]*)"\s*$', input_match)
        if not tail:
            return []
        segment = tail.group(1)
        # drop the namespace prefix group and any leading regex noise; keep the final alternation
        segment = re.sub(r"\(\?:\[\\?w-\]\+:\)\?", "", segment)
        alt = re.search(r"\(\?:([\w|-]+)\)|([\w-]+)$", segment)
        if not alt:
            return []
        body = alt.group(1) or alt.group(2) or ""
        return [p for p in body.split("|") if re.fullmatch(r"[\w-]+", p)]


if __name__ == "__main__":
    unittest.main()
