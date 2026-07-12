"""Structural and safety contracts for Magician's Codex adapters."""

from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
AUTHORING = ROOT / ".codex-plugin" / "skills"
PACKAGE = ROOT / "plugins" / "magician"
EXPLICIT_ONLY = {"almanac", "autopsy", "deploy", "inscribe", "manifest", "transmute"}


def skill_names(root: Path) -> set[str]:
    return {path.parent.name for path in root.glob("*/SKILL.md")}


class AdapterContracts(unittest.TestCase):
    def test_adapter_source_and_packaged_skill_sets_match(self) -> None:
        source = skill_names(ROOT / "skills")
        self.assertEqual(len(source), 25)
        self.assertEqual(skill_names(AUTHORING), source)
        self.assertEqual(skill_names(PACKAGE / "skills"), source)
        self.assertEqual(skill_names(PACKAGE / "source-skills"), source)

    @staticmethod
    def _strip_code(md: str) -> str:
        """Remove fenced + inline code so code snippets aren't misread as markdown links.
        e.g. `fiber.Params[int](c,"id")` or `fiber.Locals[T](c, key)` are code, not `[text](target)` links."""
        md = re.sub(r"(?ms)^[ \t]*(```|~~~).*?\1", "", md)   # fenced blocks
        md = re.sub(r"`[^`\n]*`", "", md)                     # inline code spans
        return md

    def test_packaged_adapter_links_resolve_inside_package(self) -> None:
        link_pattern = re.compile(r"\[[^]]+\]\(([^)]+)\)")
        documents = []
        for subtree in ("skills", "source-skills", "references", "lore"):
            documents.extend((PACKAGE / subtree).rglob("*.md"))
        for document in documents:
            for target in link_pattern.findall(self._strip_code(document.read_text(encoding="utf-8"))):
                if "://" in target or target.startswith("#"):
                    continue
                path = target.split("#", 1)[0]
                if not path:
                    continue
                resolved = (document.parent / path).resolve()
                with self.subTest(document=document, target=target):
                    self.assertTrue(resolved.is_relative_to(PACKAGE.resolve()))
                    self.assertTrue(resolved.exists(), resolved)

    def test_explicit_only_policy_is_preserved(self) -> None:
        configured: set[str] = set()
        for policy_file in AUTHORING.glob("*/agents/openai.yaml"):
            text = policy_file.read_text(encoding="utf-8")
            if "allow_implicit_invocation: false" in text:
                configured.add(policy_file.parents[1].name)
        self.assertEqual(configured, EXPLICIT_ONLY)

    def test_codex_adapter_does_not_request_unavailable_or_claude_actions(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in AUTHORING.glob("*/SKILL.md")
        )
        self.assertNotIn("close_agent", combined)
        self.assertNotRegex(combined, r"(?m)^# /[a-z]|`/magician:")

        statusline = (AUTHORING / "statusline" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("intentionally a no-op", statusline)
        self.assertIn("Never invoke `magician-ui`", statusline)

        chronicle = (AUTHORING / "chronicle" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("manual in Codex", chronicle)

    def test_claude_first_sources_remain_outside_generated_adapter_tree(self) -> None:
        for adapter in (PACKAGE / "skills").glob("*/SKILL.md"):
            text = adapter.read_text(encoding="utf-8")
            with self.subTest(adapter=adapter):
                self.assertNotIn("../../../skills/", text)
                if adapter.parent.name != "statusline":
                    self.assertIn("../../source-skills/", text)


if __name__ == "__main__":
    unittest.main()
