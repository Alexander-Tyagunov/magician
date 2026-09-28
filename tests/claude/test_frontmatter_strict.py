"""Strict frontmatter + least-privilege allowed-tools gate (stdlib only; optional full-YAML pass).

Directory validation blocks on frontmatter that doesn't parse or a `description` that isn't text,
and flags bare Bash / interpreter wildcards / whole-CLI grants / unscoped Write-Edit-WebFetch. The
flat `_frontmatter.py` reader strips quotes and ignores YAML typing, so it silently accepts all of
those; this gate reads every skill, agent and command with the strict subset parser in
`_strict_frontmatter.py` instead.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import _strict_frontmatter as S

ROOT = Path(__file__).resolve().parents[2]


def components() -> list[tuple[Path, str]]:
    out = [(p, "skill") for p in sorted(ROOT.glob("skills/*/SKILL.md"))]
    out += [(p, "agent") for p in sorted(ROOT.glob("agents/*.md"))]
    out += [(p, "command") for p in sorted(ROOT.glob("commands/**/*.md"))]
    # any other markdown under skills/ that opens with a frontmatter fence is also loaded as YAML
    out += [(p, "extra") for p in sorted(ROOT.glob("skills/**/*.md"))
            if p.name != "SKILL.md" and p.read_text(encoding="utf-8", errors="ignore").startswith("---\n")]
    return out


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


class StrictFrontmatterTests(unittest.TestCase):
    def test_frontmatter_is_in_the_portable_yaml_subset(self) -> None:
        for path, kind in components():
            with self.subTest(file=rel(path)):
                try:
                    S.parse_strict(path)
                except S.FrontmatterError as e:
                    self.fail(str(e).replace(str(ROOT) + "/", ""))

    def test_schema_keys_types_and_quoting(self) -> None:
        for path, kind in components():
            if kind not in ("skill", "agent"):
                continue
            try:
                fields, styles, _ = S.parse_strict(path)
            except S.FrontmatterError:
                continue  # reported by the subset test
            with self.subTest(file=rel(path)):
                self.assertEqual([], S.schema_problems(Path(rel(path)), fields, styles, kind))

    def test_allowed_tools_are_least_privilege(self) -> None:
        for path, kind in components():
            if kind != "skill":
                continue
            try:
                fields, _, _ = S.parse_strict(path)
            except S.FrontmatterError:
                continue
            for entry in S.split_tools(fields.get("allowed-tools", "")):
                with self.subTest(skill=path.parent.name, tool=entry):
                    self.assertEqual([], S.tool_problems(entry))

    def test_plugin_script_grants_point_at_executable_files(self) -> None:
        """A `Bash(${CLAUDE_SKILL_DIR}/scripts/x.sh *)` grant must name a real, executable file,
        and the skill body must invoke it by the same unquoted text so the rule can match."""
        for path, kind in components():
            if kind != "skill":
                continue
            try:
                fields, _, body = S.parse_strict(path)
            except S.FrontmatterError:
                continue
            for entry in S.split_tools(fields.get("allowed-tools", "")):
                m = re.fullmatch(r"Bash\(\$\{CLAUDE_(SKILL_DIR|PLUGIN_ROOT)\}/(\S+?)(?: \*|:\*)?\)", entry)
                if not m:
                    continue
                base = path.parent if m.group(1) == "SKILL_DIR" else ROOT
                target = base / m.group(2)
                with self.subTest(skill=path.parent.name, grant=entry):
                    self.assertTrue(target.is_file(), f"{target} missing")
                    self.assertTrue(os.access(target, os.X_OK), f"{target} not executable")
                    self.assertIn("${CLAUDE_%s}/%s" % (m.group(1), m.group(2)), body)

    def test_no_dynamic_context_injection(self) -> None:
        """`!`cmd`` / ```! blocks run at skill load, outside the permission flow, and are followed
        by the validator. Magician ships none; keep it that way (or allow only plain .sh files)."""
        pat = re.compile(r"(^|\s)!`[^`]+`|^\s*```!", re.M)
        for path, kind in components():
            if kind == "agent":
                continue
            with self.subTest(file=rel(path)):
                self.assertIsNone(pat.search(path.read_text(encoding="utf-8")))

    def test_agent_tools_are_known_and_bounded(self) -> None:
        for path, kind in components():
            if kind != "agent":
                continue
            try:
                fields, _, _ = S.parse_strict(path)
            except S.FrontmatterError:
                continue
            tools = S.split_tools(fields.get("tools", ""))
            with self.subTest(agent=path.stem):
                self.assertTrue(tools, "agent must restrict tools explicitly")
                for t in tools:
                    self.assertTrue(t in S.KNOWN or t.startswith("mcp__"), f"unknown tool {t!r}")
                    self.assertNotIn("*", t)

    def test_policy_accepts_scoped_and_rejects_broad_grants(self) -> None:
        """Pin the policy itself, so a loosened rule in _strict_frontmatter.py fails loudly. The launcher
        sample is assembled at runtime so no line here reads as an unpinned launch command."""
        launcher = "np" + "x"
        good = ["Read", "Glob", "AskUserQuestion", "mcp__context7__query-docs",
                "Edit(./.workspace/shared/**)", "Edit(~/.claude/plugins/data/magician-*/x.json)",
                "Bash(gh pr view *)", "Bash(git commit -m *)", "Bash(kg check)",
                "Bash(${CLAUDE_SKILL_DIR}/scripts/vc-start.sh *)", "WebFetch(domain:example.com)",
                "Bash(${CLAUDE_PLUGIN_ROOT}/tools/kg query *)"]
        bad = ["Bash", "Bash(*)", "Write", "Write(./docs/**)", "Monitor", "WebSearch", "WebFetch",
               "Edit", "Edit(./**)", "Edit(~/.claude/settings.json)", "Edit(${CLAUDE_PLUGIN_DATA}/x)",
               "Bash(python3 *)", "Bash(python3:*)", "Bash(node *)", "Bash(bash -c *)",
               "Bash(sh -c *)", f"Bash({launcher} tsc *)", "Bash(gh *)", "Bash(git:*)", "Bash(rm -rf *)",
               "Bash(FOO=1 jira *)", "Bash(claude mcp add *)", "Bash(ls:*)", "mcp__context7__*",
               "Bash(${CLAUDE_PLUGIN_ROOT}/tools/jira *)", "Bash(${CLAUDE_PLUGIN_ROOT}/tools/jira:*)",
               "Bash(${CLAUDE_PLUGIN_ROOT}/tools/magician-ui allow *)",
               "Bash(${CLAUDE_PLUGIN_ROOT}/tools/kg && rm x)", "Bash(${CLAUDE_PLUGIN_ROOT}/tools/../../x *)",
               "Bash(${CLAUDE_PLUGIN_ROOT}/tools/kg query $(x) *)"]
        for entry in good:
            with self.subTest(good=entry):
                self.assertEqual([], S.tool_problems(entry))
        for entry in bad:
            with self.subTest(bad=entry):
                self.assertTrue(S.tool_problems(entry), f"{entry} should be rejected")

    def test_schema_rejects_what_the_claude_ai_upload_rejects(self) -> None:
        """The claude.ai plugin upload failed on placeholders like <file> in a description."""
        def problems(**fields) -> list[str]:
            base = {"name": "x", "description": "Does x."}
            base.update(fields)
            return S.schema_problems(Path("x"), base, {k: "plain" for k in base}, "skill")
        self.assertEqual([], problems(description='Use for "blast radius of this file", a -> b.'))
        for desc in ("blast radius of <file>", "into <url/app>", "a <b>tag</b>", "x" * 1025):
            with self.subTest(description=desc[:30]):
                self.assertTrue(problems(description=desc))
        for name in ("claude-helper", "my-anthropic-tool"):
            with self.subTest(name=name):
                self.assertTrue(problems(name=name))

    # ------------------------------------------------------------ optional full-YAML pass
    def test_full_yaml_parsers_agree(self) -> None:
        """Belt and braces: if PyYAML or Ruby is on PATH, every frontmatter must load as a mapping
        whose text fields are strings, with no duplicate keys, and match the subset parser."""
        try:
            import yaml  # type: ignore
        except ImportError:
            yaml = None
        ruby = shutil.which("ruby")
        if yaml is None and ruby is None:
            self.skipTest("no PyYAML and no ruby; subset parser is authoritative")
        for path, kind in components():
            text = path.read_text(encoding="utf-8")
            fm = text[4:text.index("\n---", 4)]
            with self.subTest(file=rel(path)):
                if yaml is not None:
                    class Unique(yaml.SafeLoader):
                        pass

                    def _map(loader, node, deep=False):
                        seen = set()
                        for k, _ in node.value:
                            key = loader.construct_object(k, deep=deep)
                            if key in seen:
                                raise yaml.constructor.ConstructorError(
                                    None, None, f"duplicate key {key!r}", k.start_mark)
                            seen.add(key)
                        return yaml.SafeLoader.construct_mapping(loader, node, deep)
                    Unique.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _map)
                    data = yaml.load(fm, Loader=Unique)
                    self.assertIsInstance(data, dict)
                    for k in S.STR_KEYS & data.keys():
                        self.assertIsInstance(data[k], str, f"{k} is {type(data[k]).__name__}")
                    if kind in ("skill", "agent"):
                        try:
                            fields, _, _ = S.parse_strict(path)
                        except S.FrontmatterError:
                            fields = {}
                        for k, v in data.items():
                            if isinstance(v, (str, bool, list)):
                                self.assertEqual(v, fields.get(k), f"subset parser disagrees on {k}")
                if ruby is not None:
                    r = subprocess.run(
                        [ruby, "-ryaml", "-e",
                         "d=YAML.safe_load(STDIN.read); exit(d.is_a?(Hash) && "
                         "%w[name description argument-hint model].all?{|k| d[k].nil? || d[k].is_a?(String)} ? 0 : 3)"],
                        input=fm, text=True, capture_output=True, timeout=20)
                    self.assertEqual(0, r.returncode, r.stderr.strip()[:300])


if __name__ == "__main__":
    unittest.main()
