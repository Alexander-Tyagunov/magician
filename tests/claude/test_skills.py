"""Skill-definition contract for `skills/*/SKILL.md`.

A skill is discovered by its directory + SKILL.md frontmatter. The `name` is the invocation
handle (`/magician:<name>`) and the `description` is the only thing the model sees when deciding
whether to auto-invoke it, so both must be well-formed. Relative links in a skill body must also
resolve — a dangling `../../lore/...` link silently drops guidance the skill depends on.

`allowed-tools` pre-approves tools while the skill runs, so every entry must be scoped: no bare
Bash or WebFetch, no Write/Monitor/WebSearch at all (file writes are `Edit(<path>)` rules), and no
interpreter, package-launcher or whole-CLI grant.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

from _frontmatter import read_frontmatter
import _strict_frontmatter as S


ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"

VALID_TOOL_PREFIXES = ("mcp__",)
# Tools a skill may name in allowed-tools. Bash, Edit and WebFetch are valid only in their scoped
# forms (checked below). Write, NotebookEdit, Monitor and WebSearch are deliberately absent: a
# Write(path) rule is never consulted (Edit rules cover every file-writing tool), and Monitor and
# WebSearch cannot be scoped.
VALID_TOOLS = {
    "Read", "Edit", "Bash", "Grep", "Glob",
    "Task", "Agent", "WebFetch", "AskUserQuestion",
    "Workflow", "Skill", "TodoWrite", "LSP",
}
NEVER_GRANTED = {"Write", "NotebookEdit", "Monitor", "WebSearch"}
MUST_BE_SCOPED = {"Bash", "Edit", "WebFetch"}
# Skills that grant Grep/Glob for a narrow file set (CI files, the workspace, the plugin's own
# data) rather than code search; they are not held to the Bash search-grant set.
SEARCH_GRANT_EXEMPT = {"chronicle", "conjure", "deploy", "inscribe"}


def skill_files() -> list[Path]:
    return sorted(SKILLS.glob("*/SKILL.md"))


def bash_rule_matches(rule: str, command: str) -> bool:
    """Claude Code's matching for the text inside Bash(...): `prefix:*` matches the prefix alone or
    followed by a space; any other `*` matches any run of characters, and a single trailing ` *`
    also matches nothing at all; a rule with no `*` must equal the command."""
    m = re.fullmatch(r"(.+):\*", rule)
    if m:
        return command == m.group(1) or command.startswith(m.group(1) + " ")
    if "*" not in rule:
        return command == rule
    pattern = ".*".join(re.escape(part) for part in rule.split("*"))
    if rule.count("*") == 1 and pattern.endswith(r"\ .*"):
        pattern = pattern[: -len(r"\ .*")] + "( .*)?"
    return re.fullmatch(pattern, command, re.S) is not None


def bash_grants(skill: str) -> list[str]:
    fields, _ = read_frontmatter(SKILLS / skill / "SKILL.md")
    return [m.group(1) for entry in S.split_tools(fields.get("allowed-tools", ""))
            if (m := re.fullmatch(r"Bash\((.*)\)", entry.strip()))]


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
            for entry in S.split_tools(fields["allowed-tools"]):
                token = re.sub(r"\(.*\)$", "", entry).strip()
                with self.subTest(skill=path.parent.name, tool=token):
                    ok = token in VALID_TOOLS or token.startswith(VALID_TOOL_PREFIXES)
                    self.assertTrue(ok, f"{path.parent.name}: unknown or disallowed allowed-tool {token!r}")

    def test_allowed_tools_are_scoped(self) -> None:
        """Every grant is least-privilege: Bash/Edit/WebFetch only with a scope, never Write,
        NotebookEdit, Monitor or WebSearch, and no Bash rule that grants an interpreter (python,
        node, bash -c, ...), a package launcher (npx, uvx, ...), a whole multi-purpose CLI
        (`gh *`, `git:*`), an env-var prefix, or a Claude Code settings change."""
        for path in skill_files():
            fields, _ = read_frontmatter(path)
            if "allowed-tools" not in fields:
                continue
            for entry in S.split_tools(fields["allowed-tools"]):
                tool = re.sub(r"\(.*\)$", "", entry).strip()
                with self.subTest(skill=path.parent.name, tool=entry):
                    self.assertNotIn(tool, NEVER_GRANTED, f"{path.parent.name}: {entry!r} is never allowed")
                    if tool in MUST_BE_SCOPED:
                        self.assertNotEqual(entry, tool, f"{path.parent.name}: bare {tool} grant")
                    self.assertEqual([], S.tool_problems(entry), f"{path.parent.name}: {entry!r}")

    def test_pre_approved_commands_match_what_the_skill_runs(self) -> None:
        """A grant that never matches the command the skill tells Claude to run still prompts, so
        each command below must match one of its skill's Bash rules. Every skill with a Bash grant
        is listed, so a grant narrowed past its own command fails here."""
        SEARCH = ['ugrep -r "TODO" src', 'bfs src -name "*.ts"', 'rg -n "def main" .',
                  'grep -rn "import" src', 'find . -name "*.py"']
        runs = {
            "accelerate": [*SEARCH, 'kg query "hot path"', "kg blast src/app.ts", "kg neighbors src/app.ts"],
            "almanac": ["mkdir -p .workspace/shared/decisions .workspace/shared/specs .workspace/shared/plans"
                        " .workspace/shared/research .workspace/shared/postmortems",
                        "mkdir -p .workspace/local", "git add .workspace/shared/ CLAUDE.md .gitignore",
                        "git add REVIEW.md", "git add .claude/skills/verify/SKILL.md",
                        "git add .claude/skills/simplify/SKILL.md",
                        'git commit -m "chore: initialize magician workspace"'],
            "autopsy": ["gh run list --limit 5", 'git commit -m "docs: add post-mortem for outage"'],
            "blueprint": [*SEARCH, "kg blast src/reports/",
                          "plan-render check .workspace/shared/plans/2026-11-01-csv-export/plan.json",
                          "plan-render all .workspace/shared/plans/2026-11-01-csv-export/plan.json",
                          "${CLAUDE_PLUGIN_ROOT}/tools/plan-render all .workspace/shared/plans/x/plan.json",
                          "${CLAUDE_PLUGIN_ROOT}/tools/companion/vc-start.sh .workspace/shared/plans/x app --plan",
                          "${CLAUDE_PLUGIN_ROOT}/tools/companion/vc-stop.sh .workspace/shared/plans/x"],
            "certify": [*SEARCH, "npm test", "npm test -- login.spec.ts", "npm run lint", "npm run build", "pytest",
                        "pytest -q tests/test_auth.py", "mypy .", "ruff check .", "go test ./...", "go vet ./...",
                        "golangci-lint run", "cargo test", "cargo check", "cargo clippy", "mvn test", "gradle test"],
            "chronicle": ["ctx pct 40", 'ctx learn --add "prefer small PRs"', "ctx consolidate"],
            "confluence": ["confluence whoami", "confluence get 12345", 'confluence search "runbook"'],
            "conjure": ["${CLAUDE_SKILL_DIR}/scripts/vc-start.sh --project app",
                        'git commit -m "docs: add spec for login"',
                        'kg query "login form"'],
            "deploy": ["gh run list --branch main --limit 5", "gh run watch 123"],
            "divine": [*SEARCH, "gh pr view 42", "gh pr diff 42", "glab mr view 7", "git merge-base main HEAD", "kg check",
                       "mkdir -p .workspace/local", "touch .workspace/local/security-scan.active"],
            "inscribe": ['git commit -m "feat: add /review-sql skill"'],
            "jira": ["jira myself", "jira get PROJ-1", 'jira search "login bug"', "gh pr list --search PROJ-1"],
            "knowledge-graph": ["kg check", 'kg query "auth flow"', "kg stale", "kg refresh", "kg cache stats"],
            "magic": [*SEARCH, "kg check", 'git commit -m "docs: add research findings"'],
            "orchestrate": [*SEARCH, 'kg query "billing"', "kg blast src/billing.ts"],
            "portal": ["git worktree add ../app-login -b feature/login"],
            "scrutinize": [*SEARCH, 'kg query "auth"', "kg blast src/auth.ts"],
            "seal": ["git add -A", 'git commit -m "feat: login"', "git push -u origin HEAD",
                     'gh pr create --title "Login" --body "Adds login"', "gh pr checks 42 --watch",
                     "gh run view 99 --log-failed", "gh pr merge --squash --delete-branch"],
            "sentinel": [*SEARCH, "mkdir -p .workspace/local", "touch .workspace/local/security-scan.active",
                         "magician-scan .", "npm audit", "npm audit --json", "pip-audit", "pip-audit -f json",
                         "safety check", "govulncheck ./...", "cargo audit"],
            "statusline": ["magician-ui status", "magician-ui voice status"],
            "transmute": [*SEARCH, "kg check", 'kg query "checkout"'],
            "unravel": [*SEARCH, "kg check", "kg neighbors src/app.ts"],
            "ward": [*SEARCH],
            "weave": [*SEARCH, "kg check", "kg refresh", 'kg query "feature"'],
        }
        granting = sorted(p.parent.name for p in skill_files() if bash_grants(p.parent.name))
        self.assertEqual(granting, sorted(runs), "every skill with a Bash grant needs a row here")
        for skill, commands in runs.items():
            grants = bash_grants(skill)
            for command in commands:
                with self.subTest(skill=skill, command=command):
                    self.assertTrue(any(bash_rule_matches(g, command) for g in grants),
                                    f"/{skill}: no Bash rule in {grants} matches {command!r}")

    def test_pre_approved_rules_refuse_the_dangerous_variants(self) -> None:
        """The forms below change code, publish, rewrite history or reach past the skill's folder, so
        none may run without a prompt under the skill that grants the nearby command."""
        never = {
            "sentinel": ["npm audit fix", "npm audit fix --force", "pip-audit --fix", "cargo audit fix",
                         "govulncheck -json ./... > out"],
            "certify": ["mvn test deploy", "gradle test publish", "go test -exec /tmp/x ./...",
                        "go vet -vettool=/tmp/x ./...", "ruff check --fix .", "cargo clippy --fix",
                        "golangci-lint run --fix", "npm run lint -- --fix", "npm run build && rm x"],
            "seal": ["git push -u origin main --force", "git push -u origin +main", "git push -u origin HEAD:main",
                     "git push -u origin --delete main", "git push --force", "git push -f",
                     "git push", "git push origin main", "git push --mirror"],
            "conjure": ["open http://localhost:1 x.command", "open http://localhost.example.test/",
                        "xdg-open http://localhost@example.test/", "git add .workspace/shared/specs/",
                        "git add .workspace/shared/specs/x -f .env"],
            # Staging prompts, so a draft the user chose not to commit can't ride along with the next one.
            "autopsy": ["git add .workspace/shared/postmortems/", "git add .workspace/shared/postmortems/x -f .env"],
            "magic": ["git add .workspace/shared/research/", "git add .workspace/shared/research/x -f .env"],
            "inscribe": ["git add .claude/skills/x -f .env"],
            "almanac": ["mkdir -p .workspace/../../outside", "git add .workspace/shared/ CLAUDE.md .gitignore -f .env",
                        "git add REVIEW.md -f .env", "git add .claude/skills/", "git add .claude/skills/verify/SKILL.md .env"],
            "portal": ["mkdir -p .features/../../outside"],
            # The Monitor runs `tail` itself; the skill never pre-approves it, nor the browser opener.
            "blueprint": ["tail -n0 -F .workspace/local/plans/x/state/events.jsonl",
                          "open http://127.0.0.1:51342/magician/app/plan/",
                          "node ${CLAUDE_PLUGIN_ROOT}/tools/companion/server.cjs"],
        }
        for skill, commands in never.items():
            grants = bash_grants(skill)
            for command in commands:
                with self.subTest(skill=skill, command=command):
                    self.assertFalse(any(bash_rule_matches(g, command) for g in grants),
                                     f"/{skill}: {command!r} is pre-approved by {grants}")

    def test_rule_matcher_follows_claude_code(self) -> None:
        """The emulation above must agree with Claude Code on the forms the skills use."""
        cases = [
            ("open http://localhost:*", "open http://localhost:51234/x", False),
            ("open http://localhost:*", "open http://localhost x", True),
            ("open http://localhost*", "open http://localhost:51234/x", True),
            ("kg query *", "kg query", True),
            ("kg query *", "kg queryx", False),
            ("kg check", "kg check --json", False),
            ("git add -A", "git add -A", True),
        ]
        for rule, command, expected in cases:
            with self.subTest(rule=rule, command=command):
                self.assertEqual(expected, bash_rule_matches(rule, command))

    def test_scope_policy_distinguishes_good_and_bad_grants(self) -> None:
        """The checks above must reject the broad forms and still accept correct scoped ones. The
        launcher sample is assembled at runtime so no line here reads as an unpinned launch command."""
        launcher = "np" + "x"
        good = ["Read", "Edit(./.workspace/shared/plans/**)", "Bash(gh run list *)",
                "Bash(ctx pct *)", "Bash(${CLAUDE_SKILL_DIR}/scripts/vc-stop.sh *)",
                "WebFetch(domain:docs.example.com)", "mcp__context7__resolve-library-id"]
        bad = ["Bash", "Write", "Write(./.workspace/**)", "Monitor", "WebSearch", "WebFetch",
               "Bash(python3:*)", "Bash(python3 -c *)", "Bash(node *)", "Bash(sh -c *)",
               f"Bash({launcher} lighthouse *)", "Bash(kg:*)", "Bash(git *)"]
        for entry in good:
            with self.subTest(good=entry):
                tool = re.sub(r"\(.*\)$", "", entry)
                self.assertTrue(tool in VALID_TOOLS or tool.startswith(VALID_TOOL_PREFIXES))
                self.assertEqual([], S.tool_problems(entry))
        for entry in bad:
            with self.subTest(bad=entry):
                tool = re.sub(r"\(.*\)$", "", entry)
                rejected = (tool in NEVER_GRANTED or (tool in MUST_BE_SCOPED and entry == tool)
                            or bool(S.tool_problems(entry)))
                self.assertTrue(rejected, f"{entry} should be rejected")

    def test_mcp_grants_name_a_server_and_a_tool(self) -> None:
        """An MCP allow rule must be the full normalized name, `mcp__<server>__<tool>` or
        `mcp__<server>__*`; a bare `mcp__<server>` or `mcp__*` matches nothing (or everything) and
        silently misgrants."""
        shape = re.compile(r"^mcp__[A-Za-z0-9][A-Za-z0-9_-]*__(?:\*|[A-Za-z0-9][A-Za-z0-9_-]*)$")
        for path in skill_files():
            fields, _ = read_frontmatter(path)
            for entry in S.split_tools(fields.get("allowed-tools", "")):
                if not entry.startswith("mcp__"):
                    continue
                with self.subTest(skill=path.parent.name, grant=entry):
                    self.assertRegex(entry, shape,
                                     f"{path.parent.name}: {entry!r} must be mcp__<server>__<tool> or mcp__<server>__*")
        self.assertRegex("mcp__context7__query-docs", shape)
        self.assertRegex("mcp__playwright__*", shape)
        for bad in ("mcp__context7", "mcp__*", "mcp____x", "mcp__context7__"):
            self.assertNotRegex(bad, shape)

    def test_search_heavy_skills_pre_approve_the_embedded_search_commands(self) -> None:
        """Glob/Grep are absent by default on macOS/Linux/WSL: Claude searches with the embedded
        `bfs`/`ugrep` (and `rg`/`grep`/`find`) through Bash. A read-only skill that grants only
        Read/Grep/Glob therefore prompts on every search in manual mode, breaking the "reads never
        prompt" promise. Every skill that grants Grep or Glob must grant the Bash search set too, and
        keep Grep/Glob for sessions that restore them."""
        for path in skill_files():
            fields, _ = read_frontmatter(path)
            tools = set(S.split_tools(fields.get("allowed-tools", "")))
            if not tools & {"Grep", "Glob"} or path.parent.name in SEARCH_GRANT_EXEMPT:
                continue
            with self.subTest(skill=path.parent.name):
                self.assertTrue(S.SEARCH_GRANTS <= tools,
                                f"{path.parent.name}: missing {sorted(S.SEARCH_GRANTS - tools)}")

    def test_relative_links_resolve_inside_the_repo(self) -> None:
        link = re.compile(r"\[[^]]+\]\(([^)]+)\)")

        def anchors(md: str) -> set[str]:
            md = re.sub(r"(?ms)^[ \t]*(```|~~~).*?\1", "", md)
            slugs = {re.sub(r"[^\w\- ]", "", re.sub(r"<[^>]+>", "", line.lstrip("#")).strip().lower())
                     .replace(" ", "-") for line in md.splitlines() if re.match(r"^#{1,6} ", line)}
            return slugs | set(re.findall(r'<a id="([^"]+)"', md))

        for path in skill_files():
            _, body = read_frontmatter(path)
            for target in link.findall(_strip_code(body)):
                if "://" in target or target.startswith("#"):
                    continue
                rel, _, frag = target.partition("#")
                if not rel:
                    continue
                resolved = (path.parent / rel).resolve()
                with self.subTest(skill=path.parent.name, target=target):
                    self.assertTrue(resolved.exists(), f"dangling link {target!r} in {path.parent.name}")
                    self.assertTrue(resolved.is_relative_to(ROOT.resolve()),
                                    f"link escapes repo: {target!r}")
                    if frag and resolved.suffix == ".md":
                        self.assertIn(frag, anchors(resolved.read_text(encoding="utf-8")),
                                      f"no anchor #{frag} in {rel} (linked from {path.parent.name})")


if __name__ == "__main__":
    unittest.main()
