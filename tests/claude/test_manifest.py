"""Manifest-integrity contract for the Claude-side plugin.

A plugin that fails to load is invisible: a malformed `.claude-plugin/plugin.json`, a version that
disagrees with the marketplace entry, or a manifest that names a component directory that does not
exist all fail silently at install time. This gate makes the manifest itself testable, and keeps the
version stamped in every place a release must bump it in lock-step.

Reads declarative config + the filesystem only; runs nothing.
"""
from __future__ import annotations

import json
import re
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

    def test_marketplace_version_matches_plugin(self) -> None:
        """The marketplace entry and the plugin manifest are bumped together; a drift here ships a
        version to users that does not match what the plugin reports about itself."""
        self.assertEqual(self.marketplace["plugins"][0]["version"], self.plugin["version"])

    def test_version_is_synchronized_across_release_surfaces(self) -> None:
        """Every place a release stamps its version must agree, so `4.x` never means two things.
        Mirrors the Codex packaging gate from the Claude side so the Claude suite stands alone."""
        version = self.plugin["version"]
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        top = re.search(r"(?m)^## \[([^]]+)\]", changelog)
        self.assertIsNotNone(top, "no versioned heading in CHANGELOG.md")
        self.assertEqual(top.group(1), version, "CHANGELOG top entry != plugin version")

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        badge = re.search(r"shields\.io/badge/version-([\d.]+)-", readme)
        self.assertIsNotNone(badge, "no version badge in README.md")
        self.assertEqual(badge.group(1), version, "README badge != plugin version")

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

    def test_no_forbidden_artifacts_shipped_in_component_dirs(self) -> None:
        """The plugin's shipped surface (agents/skills/hooks/scripts) must never contain scratch or
        marketing artifacts — a distributed plugin should carry only what it runs."""
        forbidden = re.compile(r"^(X-|MEDIUM-|PRESENTATION)")
        for component in ("agents", "skills", "hooks", "scripts"):
            for path in (ROOT / component).rglob("*"):
                if path.is_file():
                    with self.subTest(path=str(path.relative_to(ROOT))):
                        self.assertFalse(forbidden.match(path.name),
                                         f"scratch/marketing artifact shipped: {path.name}")


if __name__ == "__main__":
    unittest.main()
