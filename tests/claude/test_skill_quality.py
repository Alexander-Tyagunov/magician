"""Authoring-quality contract for `skills/*/SKILL.md` and `agents/*.md`.

`test_skills.py` and `test_agents.py` prove a component is *well-formed and registrable* (the shape
Claude Code needs to load it). This gate proves it is *well-authored* — it encodes the parts of
Anthropic's current skill/subagent authoring standard that a linter can check deterministically, so
the qualities that make a skill route well and age well can't silently regress:

  * progressive disclosure (SKILL.md stays lean; deep detail moves to references/),
  * no time-sensitive prose that goes stale and is then followed confidently,
  * subagent tool grants that Claude Code will actually honor (some tools are always stripped from
    a subagent, so requesting one is a silent no-op that masks a design mistake),
  * agent names in the charset the router requires.

Sources: code.claude.com/docs/en/skills (SKILL.md authoring, ~500-line body guideline, 1,536-char
description cap), code.claude.com/docs/en/sub-agents (subagent frontmatter, always-blocked tools,
name charset). These bars are stricter than "does it parse" (`claude plugin validate`) and cheaper
than a behavioral eval — the deterministic middle tier of the quality gate.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

from _frontmatter import read_frontmatter


ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
AGENTS = ROOT / "agents"

# Anthropic's SKILL.md guidance: keep the body lean because it is a recurring per-turn token cost;
# push deep reference material into references/ loaded on demand. ~500 lines is the documented bar.
MAX_SKILL_BODY_LINES = 500

# The documented hard cap on a skill description (description + when_to_use combined).
MAX_DESCRIPTION_CHARS = 1536

# High-signal time-sensitive phrasing. A skill/agent body is a standing instruction the model
# follows confidently; a dated claim ("as of <date>", "currently") silently goes wrong once it
# ages. Domain words that are genuinely timeless ("recently added deps" as a review heuristic) are
# deliberately NOT banned — only phrasing that asserts a point-in-time truth.
STALE_PHRASE = re.compile(
    r"\b(as of \w+ \d|as of \d{4}|currently|at the moment|for now|nowadays|right now|new in v\d)\b",
    re.I,
)

# Tools Claude Code always strips from a subagent (they only make sense in the main session). A
# subagent that lists one is silently denied it, so the agent's design quietly depends on a tool it
# never gets — worse than a loud failure. Keep this in sync with code.claude.com/docs/en/sub-agents.
SUBAGENT_BLOCKED_TOOLS = {
    "Agent", "Task", "AskUserQuestion", "EndConversation",
    "EnterPlanMode", "ScheduleWakeup", "TaskOutput", "WaitForMcpServers", "Workflow",
}

# Agent `name` charset the router requires: lowercase letters/digits/hyphens, no leading hyphen, no
# ':' (reserved for plugin scoping, `magician:<name>`).
AGENT_NAME = re.compile(r"^[a-z][a-z0-9-]*$")

# Valid boolean literals Claude Code accepts for boolean frontmatter flags.
BOOL_LITERALS = {"true", "false", "yes", "no", "on", "off", "1", "0"}


def skill_files() -> list[Path]:
    return sorted(SKILLS.glob("*/SKILL.md"))


def agent_files() -> list[Path]:
    return sorted(AGENTS.glob("*.md"))


def _strip_code(md: str) -> str:
    """Drop fenced and inline code so a staleness scan reads prose, not shell snippets."""
    md = re.sub(r"(?ms)^[ \t]*(```|~~~).*?\1", "", md)
    return re.sub(r"`[^`\n]*`", "", md)


class SkillQualityTests(unittest.TestCase):
    def test_skill_bodies_respect_progressive_disclosure(self) -> None:
        """A SKILL.md body is loaded into context whenever the skill is; a bloated one taxes every
        turn it is active. Deep detail belongs in references/ loaded on demand. Keep the body under
        the documented ~500-line bar."""
        for path in skill_files():
            _, body = read_frontmatter(path)
            with self.subTest(skill=path.parent.name):
                n = len(body.splitlines())
                self.assertLessEqual(
                    n, MAX_SKILL_BODY_LINES,
                    f"{path.parent.name}: SKILL.md body is {n} lines (> {MAX_SKILL_BODY_LINES}); "
                    "move reference detail into references/ for progressive disclosure",
                )

    def test_skill_descriptions_within_hard_cap(self) -> None:
        """The router injects the description every session; the documented hard cap is 1,536 chars
        (description + when_to_use). Over it, Claude Code truncates and routing degrades."""
        for path in skill_files():
            fields, _ = read_frontmatter(path)
            desc = fields.get("description", "")
            with self.subTest(skill=path.parent.name):
                self.assertLessEqual(len(desc), MAX_DESCRIPTION_CHARS,
                                     f"{path.parent.name}: description exceeds {MAX_DESCRIPTION_CHARS} chars")

    def test_no_time_sensitive_prose_in_skills_or_agents(self) -> None:
        """A skill/agent body is a standing instruction. A point-in-time claim ("as of <date>",
        "currently …") reads as truth long after it stops being true, and the model follows it
        confidently. State durable facts; drop the timestamp."""
        for path in skill_files() + agent_files():
            _, body = read_frontmatter(path)
            name = path.parent.name if path.name == "SKILL.md" else path.stem
            hits = sorted({m.group(0).lower() for m in STALE_PHRASE.finditer(_strip_code(body))})
            with self.subTest(component=name):
                self.assertFalse(hits, f"{name}: time-sensitive phrasing {hits} — restate durably")

    def test_agents_do_not_request_subagent_blocked_tools(self) -> None:
        """Some tools are always stripped from a subagent (Task/Agent, AskUserQuestion, Workflow,
        EnterPlanMode, ScheduleWakeup, …). Requesting one is silently denied, so the agent's design
        secretly relies on a capability it never has. Catch it at authoring time, loudly."""
        for path in agent_files():
            fields, _ = read_frontmatter(path)
            tools = {t.strip() for t in fields.get("tools", "").split(",") if t.strip()}
            blocked = tools & SUBAGENT_BLOCKED_TOOLS
            with self.subTest(agent=path.stem):
                self.assertFalse(
                    blocked,
                    f"{path.stem} requests tools a subagent never receives: {sorted(blocked)}",
                )

    def test_agent_names_use_the_router_charset(self) -> None:
        """`magician:<name>` dispatch requires a name of lowercase letters/digits/hyphens with no
        leading hyphen and no ':'. A name outside the charset makes the agent un-dispatchable."""
        for path in agent_files():
            fields, _ = read_frontmatter(path)
            name = fields.get("name", "")
            with self.subTest(agent=path.stem):
                self.assertRegex(name, AGENT_NAME,
                                 f"{path.stem}: agent name {name!r} is outside the router charset")

    def test_disable_model_invocation_is_a_valid_boolean(self) -> None:
        """When a skill sets `disable-model-invocation` (command-only skills, to keep side-effecting
        skills out of the model's auto-invoke pool), the value must be a real boolean literal — a
        typo like `disable-model-invocation: ture` silently leaves the skill model-invocable."""
        for path in skill_files():
            fields, _ = read_frontmatter(path)
            val = fields.get("disable-model-invocation")
            if val is None:
                continue
            with self.subTest(skill=path.parent.name):
                self.assertIn(val.lower(), BOOL_LITERALS,
                              f"{path.parent.name}: disable-model-invocation={val!r} is not a boolean")


if __name__ == "__main__":
    unittest.main()
