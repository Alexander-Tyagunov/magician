import json
import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MARKETPLACE_FILE = REPOSITORY_ROOT / ".agents" / "plugins" / "marketplace.json"


def _marketplace_plugin_root() -> Path:
    marketplace = json.loads(MARKETPLACE_FILE.read_text(encoding="utf-8"))
    entry = marketplace["plugins"][0]
    source = entry["source"]

    assert source["source"] == "local"
    assert source["path"] == "./plugins/magician"
    return (MARKETPLACE_FILE.parent.parent.parent / source["path"]).resolve()


class CodexPackagingTests(unittest.TestCase):
    def test_marketplace_points_to_a_dedicated_package(self) -> None:
        plugin_root = _marketplace_plugin_root()

        self.assertEqual(plugin_root, REPOSITORY_ROOT / "plugins" / "magician")
        self.assertFalse(plugin_root.is_symlink())
        self.assertTrue((plugin_root / ".codex-plugin" / "plugin.json").is_file())

    def test_package_is_self_contained_and_has_no_symlinks(self) -> None:
        plugin_root = _marketplace_plugin_root()
        symlinks = [path for path in plugin_root.rglob("*") if path.is_symlink()]
        self.assertEqual(symlinks, [])

        for required in (
            "skills/almanac/SKILL.md",
            "skills/project-context/SKILL.md",
            "skills/project-context/scripts/detect_project_context.py",
            "source-skills/almanac/SKILL.md",
            "references/codex-adapter.md",
            "hooks/codex-hooks.json",
            "scripts/codex-destructive-guard.sh",
            "scripts/codex_destructive_guard.py",
            "bin/kg",
        ):
            with self.subTest(required=required):
                self.assertTrue((plugin_root / required).is_file(), required)

    def test_manifest_components_are_cache_contained(self) -> None:
        plugin_root = _marketplace_plugin_root()
        manifest_file = plugin_root / ".codex-plugin" / "plugin.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

        self.assertEqual(manifest["skills"], "./skills/")

        for field in ("skills", "hooks"):
            with self.subTest(field=field):
                component = (plugin_root / manifest[field]).resolve()
                self.assertTrue(
                    component.is_relative_to(plugin_root),
                    f"{field} resolves outside the cached plugin root: {component}",
                )
                self.assertTrue(
                    component.exists(), f"missing declared {field} component: {component}"
                )

        adapters = list((plugin_root / manifest["skills"]).glob("*/SKILL.md"))
        self.assertEqual(len(adapters), 26)
        source_skills = list((plugin_root / "source-skills").glob("*/SKILL.md"))
        self.assertEqual(len(source_skills), 25)

    def test_generated_package_is_synchronized(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(REPOSITORY_ROOT / ".codex-plugin" / "scripts" / "build_package.py"),
                "--check",
            ],
            cwd=REPOSITORY_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_codex_clis_keep_secrets_out_of_process_arguments(self) -> None:
        plugin_root = _marketplace_plugin_root()
        for name in ("jira", "confluence"):
            with self.subTest(name=name):
                text = (plugin_root / "bin" / name).read_text(encoding="utf-8")
                self.assertIn('os.environ.get("MAGICIAN_HOME")', text)
                self.assertIn('os.environ["CODEX_HOME"]', text)
                self.assertIn('".codex", "magician"', text)
                self.assertNotIn('os.environ.get("CLAUDE_PLUGIN_DATA")', text)
                self.assertNotIn('"Authorization: " + _auth()', text.split("cmd =", 1)[1])
                self.assertIn('"-H", "@-"', text)
                self.assertIn("input=headers", text)

    def test_codex_stateful_clis_never_default_to_claude_state(self) -> None:
        plugin_root = _marketplace_plugin_root()
        for name in ("jira", "confluence", "kg", "ctx"):
            with self.subTest(name=name):
                text = (plugin_root / "bin" / name).read_text(encoding="utf-8")
                self.assertIn("CODEX_HOME", text)
                self.assertNotIn('os.path.join(HOME, ".claude", "magician")', text)
                self.assertNotIn('os.environ.get("CLAUDE_PLUGIN_DATA")', text)


if __name__ == "__main__":
    unittest.main()
