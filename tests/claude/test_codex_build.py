"""Codex / ChatGPT package build (scripts/build-codex.sh).

Builds the package twice into temporary folders and checks the result: the layout, the root
plugin.json and its extensions.com.openai block, the marketplace entry, Agent Skills (AAIF)-only
frontmatter, one lens skill per agent, no hooks, links that resolve inside the package, no
unrewritten plugin variables, the environment-based Jira/Confluence settings, and that two builds
are byte-identical. Stdlib only; no network.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _frontmatter import read_frontmatter  # noqa: E402

BUILD = ROOT / "scripts" / "build-codex.sh"
AAIF = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
DROPPED = ("hooks", "monitors", "output-styles", "mods", ".claude-plugin", "tests", "evals", "scripts",
           "agents", "commands")
LINK = re.compile(r"\]\(([^)\s]+)\)")
PATH_TARGET = re.compile(r"^(?:[\w.-]*/[\w./<>-]*|[\w-][\w.-]*\.[A-Za-z0-9]+)(?:#[\w.-]*)?$")
FENCE = re.compile(r"(?ms)^[ \t]*```.*?^[ \t]*```[^\n]*$")
CLAUDE_VAR = re.compile(r"\$\{?CLAUDE_[A-Z_]+")
EXCLUDED_SKILLS = ("statusline",)
EXCLUDED_TOOLS = ("magician-statusline", "magician-ui")
SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
GUARD_NOTE = "this package ships no hooks; the destructive guard is Claude Code only."


def build(out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(BUILD), "--out", str(out)], capture_output=True, text=True,
                          timeout=120)


def snapshot(base: Path) -> dict[str, tuple[bytes, int]]:
    return {p.relative_to(base).as_posix(): (p.read_bytes(), p.stat().st_mode & 0o777)
            for p in sorted(base.rglob("*")) if p.is_file()}


class CodexBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        cls.out = tmp / "a" / "magician"
        cls.out2 = tmp / "b" / "magician"
        cls.run1 = build(cls.out)
        cls.run2 = build(cls.out2)
        cls.manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def setUp(self) -> None:
        self.assertEqual(self.run1.returncode, 0, self.run1.stdout + self.run1.stderr)
        self.assertEqual(self.run2.returncode, 0, self.run2.stdout + self.run2.stderr)

    def test_build_reports_a_valid_package(self) -> None:
        self.assertIn("package valid", self.run1.stdout)

    def test_layout(self) -> None:
        for rel in ("plugin.json", "README.md", "LICENSE", "skills", "lore", "lore/deep", "tools"):
            with self.subTest(path=rel):
                self.assertTrue((self.out / rel).exists(), rel)
        for rel in DROPPED:
            with self.subTest(dropped=rel):
                self.assertFalse((self.out / rel).exists(), f"{rel}/ must not ship in the Codex package")
        self.assertFalse(list(self.out.rglob("hooks.json")))
        self.assertFalse(list(self.out.rglob("__pycache__")))

    def test_manifest(self) -> None:
        plugin = json.loads((self.out / "plugin.json").read_text(encoding="utf-8"))
        for key in ("name", "version", "author", "homepage", "repository", "license", "keywords"):
            with self.subTest(key=key):
                self.assertEqual(plugin[key], self.manifest[key])
        self.assertNotIn("userConfig", plugin)
        self.assertNotIn("Claude Code", plugin["description"])
        openai = plugin["extensions"]["com.openai"]
        ui = openai["interface"]
        self.assertEqual(ui["displayName"], "Magician")
        for key in ("shortDescription", "category", "capabilities", "defaultPrompt"):
            with self.subTest(key=key):
                self.assertTrue(ui[key], key)
        self.assertFalse({"logo", "screenshots", "composerIcon"} & set(ui), "no image files to point at")
        self.assertEqual(plugin["$schema"], SCHEMA)
        self.assertEqual(openai["onboardingSkill"], "./skills/almanac/SKILL.md")
        self.assertTrue((self.out / openai["onboardingSkill"]).is_file())

    def test_marketplace_entry(self) -> None:
        market = json.loads((self.out.parent / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        # Only the keys OpenAI's "Package your plugin" marketplace.json example shows.
        self.assertEqual(set(market), {"name", "interface", "plugins"})
        self.assertEqual(set(market["interface"]), {"displayName"})
        (entry,) = market["plugins"]
        self.assertEqual(set(entry), {"name", "source", "policy", "category"})
        self.assertEqual(entry["name"], "magician")
        self.assertEqual(entry["source"]["path"], "./magician")
        self.assertEqual(entry["policy"], {"installation": "AVAILABLE", "authentication": "ON_INSTALL"})
        self.assertTrue(entry["category"])
        self.assertTrue((self.out.parent / entry["source"]["path"] / "plugin.json").is_file())

    def test_every_skill_and_agent_ships_as_a_skill(self) -> None:
        skills = sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")
                        if p.parent.name not in EXCLUDED_SKILLS)
        agents = sorted(p.stem for p in (ROOT / "agents").glob("*.md"))
        built = sorted(p.parent.name for p in (self.out / "skills").glob("*/SKILL.md"))
        self.assertEqual(built, sorted(skills + [a + "-lens" for a in agents]))
        for a in agents:
            with self.subTest(agent=a):
                fields, body = read_frontmatter(self.out / "skills" / f"{a}-lens" / "SKILL.md")
                self.assertTrue(fields["description"].startswith(f"Use as a {a} review lens"))
                _, src_body = read_frontmatter(ROOT / "agents" / f"{a}.md")
                first_heading = next(l for l in src_body.splitlines() if l.startswith("# "))
                self.assertIn(first_heading, body)

    def test_frontmatter_is_aaif_only(self) -> None:
        for sk in sorted(self.out.glob("skills/*/SKILL.md")):
            fields, _ = read_frontmatter(sk)
            with self.subTest(skill=sk.parent.name):
                self.assertLessEqual(set(fields), AAIF, f"non-AAIF keys: {sorted(set(fields) - AAIF)}")
                self.assertEqual(fields["name"], sk.parent.name)
                self.assertTrue(0 < len(fields["description"]) <= 1024)
                if "metadata" in fields:
                    meta = json.loads(fields["metadata"])
                    self.assertTrue(all(isinstance(k, str) and isinstance(v, str) for k, v in meta.items()))

    def test_claude_code_keys_move_to_metadata(self) -> None:
        fields, _ = read_frontmatter(self.out / "skills" / "divine" / "SKILL.md")
        self.assertEqual(json.loads(fields["metadata"])["claude-code.effort"], "high")
        fields, _ = read_frontmatter(self.out / "skills" / "deploy" / "SKILL.md")
        meta = json.loads(fields["metadata"])
        self.assertEqual(meta["claude-code.disable-model-invocation"], "true")
        self.assertIn(".github/**", json.loads(meta["claude-code.paths"]))

    def test_no_unrewritten_plugin_variables(self) -> None:
        checked = 0
        for f in sorted(self.out.rglob("*")):
            if not f.is_file():
                continue
            text = f.read_bytes().decode("utf-8", "ignore")
            with self.subTest(file=f.relative_to(self.out).as_posix()):
                self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", text)
                self.assertNotIn("${CLAUDE_SKILL_DIR}", text)
                if f.suffix == ".md":
                    checked += 1
                    self.assertEqual(CLAUDE_VAR.findall(text), [])
        self.assertGreater(checked, 50)

    def test_claude_only_session_and_data_paths_are_rewritten(self) -> None:
        chronicle = (self.out / "skills" / "chronicle" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("session transcripts are Claude Code only", chronicle)
        self.assertNotIn("CLAUDE_SESSION_ID", chronicle)
        prefs = (self.out / "lore" / "integration-prefs.md").read_text(encoding="utf-8")
        self.assertIn('PREFS="${MAGICIAN_DATA:-$HOME/.local/share/magician}/integration-prefs.json"', prefs)
        mgmt = (self.out / "skills" / "chronicle" / "references" / "context-mgmt.md").read_text(encoding="utf-8")
        self.assertEqual(mgmt.count("> On Codex: session transcripts (`~/.claude/projects/`) are Claude Code only"), 1)

    def test_codex_package_does_not_claim_the_guard(self) -> None:
        for f in sorted(list(self.out.glob("skills/**/*.md")) + list(self.out.glob("lore/**/*.md"))):
            text = f.read_text(encoding="utf-8")
            with self.subTest(file=f.relative_to(self.out).as_posix()):
                self.assertNotIn("unconditionally blocks", text)
                self.assertNotRegex(text, r"magician ships a `PreToolUse")
                if re.search(r"destructive[- ]guard", text, re.I):
                    self.assertEqual(text.lower().count(GUARD_NOTE.lower()), 1)
        sentinel = (self.out / "skills" / "sentinel" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("this Codex package ships no hooks, so nothing here blocks them", sentinel)
        self.assertIn(GUARD_NOTE, (self.out / "lore" / "autonomy.md").read_text(encoding="utf-8"))
        # The source keeps the Claude Code claim: the guard ships there.
        self.assertIn("unconditionally blocks", (ROOT / "skills" / "sentinel" / "SKILL.md").read_text(encoding="utf-8"))

    def test_validation_fails_on_a_claude_variable(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import build_codex  # type: ignore
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "magician"
            build_codex.build(out)
            self.assertEqual(build_codex.validate(out), [])
            for planted in ("$CLAUDE_PROJECT_DIR", "${CLAUDE_SESSION_ID}"):
                (out / "lore" / "planted.md").write_text(f"see {planted}\n", encoding="utf-8")
                with self.subTest(planted=planted):
                    problems = build_codex.validate(out)
                    self.assertTrue(any("lore/planted.md:1: Claude Code variable" in p for p in problems), problems)

    def test_claude_only_status_line_is_left_out(self) -> None:
        for name in EXCLUDED_SKILLS:
            self.assertFalse((self.out / "skills" / name).exists(), name)
        for name in EXCLUDED_TOOLS:
            self.assertFalse((self.out / "tools" / name).exists(), name)
        readme = (self.out / "README.md").read_text(encoding="utf-8")
        for word in ("`statusline` skill", "`magician-statusline`", "`magician-ui`"):
            self.assertIn(word, readme)

    def test_links_resolve_inside_the_package(self) -> None:
        checked = 0
        for f in sorted(list(self.out.glob("skills/**/*.md")) + list(self.out.glob("lore/**/*.md"))):
            for target in LINK.findall(FENCE.sub("", f.read_text(encoding="utf-8"))):
                if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith(("#", "<")):
                    continue
                if not PATH_TARGET.match(target):
                    continue
                path = target.split("#", 1)[0]
                resolved = (f.parent / path).resolve()
                with self.subTest(file=f.relative_to(self.out).as_posix(), link=target):
                    self.assertTrue(resolved.exists(), "broken link")
                    self.assertTrue(resolved.is_relative_to(self.out.resolve()), "link leaves the package")
                checked += 1
        self.assertGreater(checked, 100)

    def test_skills_get_a_codex_footer(self) -> None:
        text = (self.out / "skills" / "conjure" / "SKILL.md").read_text(encoding="utf-8")
        footer = text.split("\n## On Codex\n", 1)[1]
        self.assertIn("`AskUserQuestion`", footer)
        self.assertIn("../../lore/skill-authoring.md#on-codex", footer)
        self.assertIn("../../tools/kg", text)
        lore = (ROOT / "lore" / "skill-authoring.md").read_text(encoding="utf-8")
        self.assertIn("\n## On Codex\n", lore)
        for term in ("`/goal`", "`Workflow`", ".codex/agents/*.toml", "`AskUserQuestion`",
                     "--sandbox workspace-write", "`Monitor`", "`AGENTS.md`"):
            with self.subTest(term=term):
                self.assertIn(term, lore.split("\n## On Codex\n", 1)[1])

    def test_relative_layout_keeps_wrappers_working(self) -> None:
        wrapper = self.out / "skills" / "conjure" / "scripts" / "vc-start.sh"
        self.assertTrue(os.access(wrapper, os.X_OK))
        self.assertTrue((wrapper.parent / ".." / ".." / ".." / "tools" / "companion" / "vc-start.sh").resolve().is_file())
        for tool in ("kg", "jira", "confluence", "ctx", "plan-render"):
            with self.subTest(tool=tool):
                self.assertTrue(os.access(self.out / "tools" / tool, os.X_OK))

    def test_jira_and_confluence_read_environment_variables(self) -> None:
        env = {"PATH": os.environ.get("PATH", ""), "HOME": tempfile.gettempdir()}
        for tool, var in (("jira", "MAGICIAN_JIRA_BASE_URL"), ("confluence", "MAGICIAN_CONFLUENCE_BASE_URL")):
            src = (self.out / "tools" / tool).read_text(encoding="utf-8")
            with self.subTest(tool=tool):
                self.assertNotIn("CLAUDE_PLUGIN_OPTION_", src)
                self.assertIn(f'os.environ.get("{var}")', src)
                r = subprocess.run([sys.executable, str(self.out / "tools" / tool), "whoami" if tool == "confluence" else "myself"],
                                   capture_output=True, text=True, env=env, timeout=30)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(var, r.stderr + r.stdout)

    def test_two_builds_are_byte_identical(self) -> None:
        self.assertEqual(snapshot(self.out), snapshot(self.out2))
        self.assertEqual((self.out.parent / ".agents" / "plugins" / "marketplace.json").read_bytes(),
                         (self.out2.parent / ".agents" / "plugins" / "marketplace.json").read_bytes())

    def test_refuses_to_replace_a_foreign_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "magician"
            target.mkdir()
            (target / "keep.txt").write_text("not a build\n", encoding="utf-8")
            r = build(target)
            self.assertNotEqual(r.returncode, 0)
            self.assertTrue((target / "keep.txt").is_file())

    def test_build_output_is_gitignored(self) -> None:
        r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "--no-index", "dist/codex/magician/plugin.json"],
                           capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "dist/codex/magician/plugin.json")


if __name__ == "__main__":
    unittest.main()
