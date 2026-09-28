"""Manifest-integrity contract for the Claude-side plugin.

A plugin that fails to load is invisible: a malformed `.claude-plugin/plugin.json`, a marketplace
entry that redeclares `version` (which the manifest silently overrides), or a manifest that names a
component directory that does not exist all fail silently at install time. This gate makes the
manifest itself testable, and keeps the version stamped in every place a release must bump it in
lock-step.

Reads declarative config + the filesystem only; runs nothing.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = ROOT / ".claude-plugin"
PLUGIN_JSON = PLUGIN_DIR / "plugin.json"
MARKETPLACE_JSON = PLUGIN_DIR / "marketplace.json"

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


class ManifestIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
        cls.marketplace = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))

    def test_plugin_manifest_has_required_identity(self) -> None:
        for key in ("name", "version", "description"):
            with self.subTest(key=key):
                self.assertIn(key, self.plugin)
                self.assertTrue(str(self.plugin[key]).strip(), f"empty {key}")
        self.assertEqual(self.plugin["name"], "magician")

    def test_version_is_semver(self) -> None:
        self.assertRegex(self.plugin["version"], SEMVER)

    def test_marketplace_is_well_formed(self) -> None:
        self.assertEqual(self.marketplace["name"], "magician")
        plugins = self.marketplace.get("plugins")
        self.assertTrue(plugins and isinstance(plugins, list), "no plugins listed")
        self.assertEqual(plugins[0]["name"], "magician")

    def test_marketplace_entry_omits_version(self) -> None:
        """Single source of truth: the version lives only in plugin.json. Claude Code always uses the
        manifest value and silently ignores a marketplace `version`, so carrying it in both risks a
        stale marketplace value masking a real bump (see code.claude.com/docs version management)."""
        self.assertNotIn("version", self.marketplace["plugins"][0],
                         "marketplace entry must not carry version; plugin.json is authoritative")

    def test_marketplace_description_matches_manifest(self) -> None:
        """The marketplace entry and the manifest describe the same plugin in the same words, so a
        listing never advertises less (or more) than the plugin that installs."""
        self.assertEqual(self.marketplace["plugins"][0].get("description"), self.plugin["description"])

    def test_version_is_synchronized_across_release_surfaces(self) -> None:
        """Every place a release stamps its version must agree, so `4.x` never means two things."""
        version = self.plugin["version"]
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        top = re.search(r"(?m)^## \[([^]]+)\]", changelog)
        self.assertIsNotNone(top, "no versioned heading in CHANGELOG.md")
        self.assertEqual(top.group(1), version, "CHANGELOG top entry != plugin version")

        # The README carries no version stamp to keep in sync: it has no badges and no remote images
        # (the plugin directory accepts Markdown images of bundled files only).
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotRegex(readme, r"(?i)shields\.io", "README.md must not carry a shields.io badge")
        remote = re.findall(r"!\[[^\]]*\]\(\s*<?((?:https?:)?//[^)\s>]+)", readme)
        remote += re.findall(r"(?i)<img\b[^>]*\bsrc\s*=\s*[\"']?((?:https?:)?//[^\"'\s>]+)", readme)
        self.assertEqual(remote, [], f"README.md must not reference remote images: {remote}")

    def test_declared_component_dirs_exist(self) -> None:
        """The runtime discovers agents/, skills/, and hooks/ by convention. If the manifest names a
        component path explicitly, it must resolve inside the plugin; the conventional dirs must exist."""
        for field in ("agents", "skills", "hooks", "commands"):
            value = self.plugin.get(field)
            if not value:
                continue
            rel = value.lstrip("./") if isinstance(value, str) else None
            if rel is None:
                continue
            resolved = (ROOT / rel).resolve()
            with self.subTest(field=field):
                self.assertTrue(resolved.exists(), f"manifest {field} -> missing {value}")
                self.assertTrue(resolved.is_relative_to(ROOT.resolve()),
                                f"manifest {field} escapes plugin root: {value}")

        # Conventional component dirs the plugin actually ships.
        for conventional in ("agents", "skills", "hooks", "scripts"):
            with self.subTest(dir=conventional):
                self.assertTrue((ROOT / conventional).is_dir(),
                                f"missing conventional component dir: {conventional}/")

    def test_codex_marketplace_points_at_codex_plugin_branch(self) -> None:
        """Codex installs from the generated package on the `codex-plugin` branch. Main keeps only the
        marketplace entry that points there, so no Codex build output may come back onto main."""
        codex = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(len(codex["plugins"]), 1)
        source = codex["plugins"][0]["source"]
        self.assertEqual(source["source"], "git-subdir")
        self.assertEqual(source["ref"], "codex-plugin")
        self.assertEqual(source["path"], "./plugins/magician")
        self.assertEqual(source["url"], self.plugin["repository"] + ".git")
        for rel in (".codex-plugin", "plugins", "tests/codex", "hooks/codex-hooks.json",
                    "scripts/codex-destructive-guard.sh", "scripts/codex_destructive_guard.py"):
            path = ROOT / rel
            files = [path] if path.is_file() else [
                p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
            with self.subTest(path=rel):
                self.assertEqual(files, [], f"Codex build output belongs on the codex-plugin branch: {rel}")

    def test_no_forbidden_artifacts_are_tracked(self) -> None:
        """The plugin folder is the repo root, so every tracked file ships. Scratch and marketing
        drafts, local tool state and OS junk must never be tracked anywhere in it, nor sit untracked
        where .gitignore misses them (the next `git add -A` would stage them)."""
        forbidden_name = re.compile(r"^(X-|MEDIUM-|PRESENTATION|TRANSMUTE-)|^gemini_generated\.png$"
                                    r"|^(\.DS_Store|Thumbs\.db|desktop\.ini)$")
        forbidden_dir = {".workspace", ".claude", ".codex", "__MACOSX", "__pycache__"}
        tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others",
                                  "--exclude-standard"], capture_output=True, text=True, check=True).stdout.split("\0")
        self.assertGreater(len(tracked), 50)
        for rel in filter(None, tracked):
            parts = rel.split("/")
            with self.subTest(path=rel):
                self.assertFalse(forbidden_name.search(parts[-1]), f"scratch or junk file tracked: {rel}")
                self.assertFalse(forbidden_dir & set(parts[:-1]), f"local state tracked: {rel}")

    def test_gitignore_keeps_local_scratch_out(self) -> None:
        """A plain `git add -A` (which /seal runs) must not pick up the local drafts and tool state."""
        names = ["X-thread.md", "MEDIUM-post.md", "PRESENTATION_v2.md", "TRANSMUTE-notes.md",
                 "gemini_generated.png", ".workspace/shared/specs/a.md", ".claude/launch.json",
                 ".codex/CODEX-TEST.md", "skills/x/.DS_Store", "__MACOSX/a", "desktop.ini",
                 "skills/magic/MEDIUM-notes.md", "agents/X-thread.md", "lore/PRESENTATION.md",
                 "docs/TRANSMUTE-x.md", "assets/gemini_generated.png"]
        out = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "--no-index", *names],
                             capture_output=True, text=True).stdout.split()
        self.assertEqual(sorted(out), sorted(names))


if __name__ == "__main__":
    unittest.main()
