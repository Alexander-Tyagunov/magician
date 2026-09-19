"""Skill-definition contract for `skills/*/SKILL.md`.

A skill is discovered by its directory + SKILL.md frontmatter. The `name` is the invocation
handle (`/magician:<name>`) and the `description` is the only thing the model sees when deciding
whether to auto-invoke it, so both must be well-formed. Relative links in a skill body must also
resolve — a dangling `../../lore/...` link silently drops guidance the skill depends on.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

from _frontmatter import read_frontmatter


ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"

VALID_TOOL_PREFIXES = ("mcp__",)
VALID_TOOLS = {
    "Read", "Write", "Edit", "NotebookEdit",
    "Bash", "Grep", "Glob",
    "Task", "WebFetch", "WebSearch", "AskUserQuestion",
    "Monitor", "Workflow",
}


def skill_files() -> list[Path]:
    return sorted(SKILLS.glob("*/SKILL.md"))


def _strip_code(md: str) -> str:
    md = re.sub(r"(?ms)^[ \t]*(```|~~~).*?\1", "", md)
    md = re.sub(r"`[^`\n]*`", "", md)
    return md


class SkillDefinitionTests(unittest.TestCase):
    def test_there_are_skills(self) -> None:
        self.assertGreaterEqual(len(skill_files()), 20)

    def test_every_skill_has_name_and_description(self) -> None:
        for path in skill_files():
            with self.subTest(skill=path.parent.name):
                fields, body = read_frontmatter(path)
                self.assertIn("name", fields)
                self.assertIn("description", fields)
                self.assertTrue(body, "empty skill body")

    def test_name_matches_directory(self) -> None:
        for path in skill_files():
            with self.subTest(skill=path.parent.name):
                fields, _ = read_frontmatter(path)
                self.assertEqual(fields["name"], path.parent.name)

    def test_description_length_is_within_bounds(self) -> None:
        """Skill descriptions are injected into the router's context every session; an over-long
        one is a token tax on every turn. Claude Code's practical ceiling is ~1024 chars."""
        for path in skill_files():
            with self.subTest(skill=path.parent.name):
                fields, _ = read_frontmatter(path)
                desc = fields["description"]
                self.assertGreaterEqual(len(desc), 20)
                self.assertLessEqual(len(desc), 1024)

    def test_allowed_tools_use_known_identifiers(self) -> None:
        """`allowed-tools` is optional (a doc-only skill may omit it), but when present every
        entry must be a real tool or an mcp__ identifier — a typo grants nothing."""
        for path in skill_files():
            fields, _ = read_frontmatter(path)
            if "allowed-tools" not in fields:
                continue
            for raw in fields["allowed-tools"].split(","):
                token = re.sub(r"\([^)]*\)", "", raw).strip()
                if not token:
                    continue
                with self.subTest(skill=path.parent.name, tool=token):
                    ok = token in VALID_TOOLS or token.startswith(VALID_TOOL_PREFIXES)
                    self.assertTrue(ok, f"{path.parent.name}: unknown allowed-tool {token!r}")

    def test_relative_links_resolve_inside_the_repo(self) -> None:
        link = re.compile(r"\[[^]]+\]\(([^)]+)\)")
        for path in skill_files():
            _, body = read_frontmatter(path)
            for target in link.findall(_strip_code(body)):
                if "://" in target or target.startswith("#"):
                    continue
                rel = target.split("#", 1)[0]
                if not rel:
                    continue
                resolved = (path.parent / rel).resolve()
                with self.subTest(skill=path.parent.name, target=target):
                    self.assertTrue(resolved.exists(), f"dangling link {target!r} in {path.parent.name}")
                    self.assertTrue(resolved.is_relative_to(ROOT.resolve()),
                                    f"link escapes repo: {target!r}")


if __name__ == "__main__":
    unittest.main()
