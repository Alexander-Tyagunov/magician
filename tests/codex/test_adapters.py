"""Structural and safety contracts for Magician's Codex adapters."""

from __future__ import annotations

from pathlib import Path
import re
import unittest

from _main import main_source


ROOT = Path(__file__).resolve().parents[2]
AUTHORING = ROOT / ".codex-plugin" / "skills"
PACKAGE = ROOT / "plugins" / "magician"
EXPLICIT_ONLY = {"almanac", "autopsy", "deploy", "inscribe", "manifest", "transmute"}
CODEX_ONLY = {"project-context"}
# Dangling anchors that come unchanged from main's own files (fix them on main, then drop the entry).
KNOWN_MAIN_DANGLING: set = set()
_ANCHOR_TAG = re.compile(r"""<a\s+(?:id|name)=["']([^"']+)["']""")


def github_slug(heading: str) -> str:
    text = _ANCHOR_TAG.sub("", heading)
    text = re.sub(r"<[^>]+>", "", text).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors_in(document: Path) -> set[str]:
    anchors: set[str] = set()
    seen: dict[str, int] = {}
    fence = None
    for line in document.read_text(encoding="utf-8").splitlines():
        marker = re.match(r"^[ \t]*(```|~~~)", line)
        if marker:
            fence = None if fence == marker.group(1) else (fence or marker.group(1))
            continue
        if fence:
            continue
        anchors.update(_ANCHOR_TAG.findall(line))
        heading = re.match(r"^#{1,6}\s+(.*)$", line)
        if heading:
            slug = github_slug(heading.group(1))
            count = seen.get(slug, 0)
            seen[slug] = count + 1
            anchors.add(slug if count == 0 else f"{slug}-{count}")
    return anchors


def skill_names(root: Path) -> set[str]:
    return {path.parent.name for path in root.glob("*/SKILL.md")}


class AdapterContracts(unittest.TestCase):
    def test_adapter_source_and_packaged_skill_sets_match(self) -> None:
        source = skill_names(main_source() / "skills")
        self.assertEqual(len(source), 25)
        self.assertEqual(skill_names(AUTHORING), source | CODEX_ONLY)
        self.assertEqual(skill_names(PACKAGE / "skills"), source | CODEX_ONLY)
        self.assertEqual(skill_names(PACKAGE / "source-skills"), source)

    def test_project_context_is_codex_only_and_routes_packaged_lore(self) -> None:
        skill = AUTHORING / "project-context"
        packaged = PACKAGE / "skills" / "project-context"

        self.assertTrue((skill / "scripts" / "detect_project_context.py").is_file())
        self.assertTrue((packaged / "scripts" / "detect_project_context.py").is_file())
        text = (skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Codex-only", text)
        self.assertIn("recommended_deep_dives", text)
        self.assertNotIn("source-skills/project-context", text)
        self.assertFalse((main_source() / "skills" / "project-context").exists())
        self.assertNotIn(
            "project-context",
            (main_source() / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"),
        )

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
                path, _, anchor = target.partition("#")
                if not path:
                    continue
                resolved = (document.parent / path).resolve()
                with self.subTest(document=document, target=target):
                    self.assertTrue(resolved.is_relative_to(PACKAGE.resolve()))
                    self.assertTrue(resolved.exists(), resolved)
                    relative = document.relative_to(PACKAGE).as_posix()
                    if anchor and resolved.suffix == ".md" and (relative, target) not in KNOWN_MAIN_DANGLING:
                        self.assertIn(anchor, anchors_in(resolved), f"dangling anchor {target} in {relative}")

    def test_codex_lore_overlays_keep_every_linked_anchor(self) -> None:
        """Skills are shared: every anchor main links to in models.md/model-behavior.md must exist in
        the Codex overlays too (a heading rename needs a compat <a id>)."""
        link_pattern = re.compile(r"\]\(([^)#]*lore/(models|model-behavior)\.md)#([^)]+)\)")
        documents = [
            path
            for subtree in ("skills", "source-skills", "references", "lore")
            for path in (PACKAGE / subtree).rglob("*.md")
        ]
        linked = 0
        for document in documents:
            for _path, name, anchor in link_pattern.findall(self._strip_code(document.read_text(encoding="utf-8"))):
                linked += 1
                overlay = ROOT / ".codex-plugin" / "lore" / f"{name}.md"
                with self.subTest(document=document.relative_to(PACKAGE).as_posix(), anchor=anchor):
                    self.assertIn(anchor, anchors_in(overlay))
        self.assertGreater(linked, 0)

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

        adapter = (ROOT / ".codex-plugin" / "references" / "codex-adapter.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Codex model and reasoning guidance", adapter)
        self.assertIn(".codex-plugin/lore/models.md", adapter)
        self.assertIn("never apply Claude model aliases", adapter)

    def test_claude_first_sources_remain_outside_generated_adapter_tree(self) -> None:
        for adapter in (PACKAGE / "skills").glob("*/SKILL.md"):
            text = adapter.read_text(encoding="utf-8")
            with self.subTest(adapter=adapter):
                self.assertNotIn("../../../skills/", text)
                if adapter.parent.name not in {"project-context", "statusline"}:
                    self.assertIn("../../source-skills/", text)


if __name__ == "__main__":
    unittest.main()
