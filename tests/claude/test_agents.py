"""Agent-definition contract for `agents/*.md`.

These are the subagents Claude Code discovers and spawns (via the Task tool / `magician:<name>`).
A malformed frontmatter field means Claude Code silently fails to register the agent, so this
gate enforces the shape of a well-formed, spawnable agent — the same bar Anthropic applies to
plugin subagents: a stable `name`, a description that tells the router when to use it, a least-
privilege `tools` list, and an explicit `model`.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))  # importable as tests.claude.test_agents
from _frontmatter import read_frontmatter


ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "agents"
SKILLS = ROOT / "skills"

REQUIRED_FIELDS = {"name", "description", "tools", "model"}

# Tool identifiers a magician subagent may request. MCP tools are namespaced `mcp__…`.
VALID_TOOLS = {"Read", "Write", "Edit", "Bash", "Grep", "Glob"}

# The only Bash specifiers a read-only lens may carry: the knowledge graph's read commands, which return
# ranked `file:line` for far fewer tokens than grepping. Each is a scoped allowlist rule (`Bash(kg query *)`),
# never bare `Bash` — `kg init`/`refresh`/`reset` and every other command stay out of reach.
KG_READ_GRANTS = {"Bash(kg check)", "Bash(kg query *)", "Bash(kg blast *)", "Bash(kg neighbors *)"}

# Never in an agent's `tools:` list: the wildcard would hand an agent every tool, and the rest are
# unscoped network egress or background execution no magician agent needs.
FORBIDDEN_TOOLS = {"*", "Monitor", "WebFetch", "WebSearch", "NotebookEdit"}

# `tools:` limits what an agent may use. Read-only is the default; an agent gets more only when
# its job cannot be done without it, and that exception is spelled out here so widening an agent
# is a deliberate, reviewed change to this map.
READ_ONLY = {"Read", "Grep", "Glob"} | KG_READ_GRANTS
MAX_TOOLS = {
    # Applies one verified fix and reruns the acceptance check: must edit and run commands.
    "fixer": {"Read", "Edit", "Write", "Grep", "Glob", "Bash"},
    # Runs the repo's gates and reads their exit codes; writes nothing.
    "gatekeeper": {"Read", "Grep", "Glob", "Bash"},
}

# Review lenses report findings; they never mutate code or run commands.
REVIEW_LENSES = ("guardian", "reviewer", "sentinel", "simplifier", "verifier")

# Model aliases Claude Code accepts in agent frontmatter (plus `inherit` and concrete claude-* ids).
VALID_MODEL_ALIASES = {"opus", "sonnet", "haiku", "fable", "inherit"}

# Lenses that keep project memory (`memory: project` -> `.claude/agent-memory/<agent>/`, tracked by git
# by default; code.claude.com/docs/en/sub-agents "memory"). Memory also hands the agent Read/Write/Edit
# for its memory files, so each of these bodies must restate that it changes no code.
MEMORY_LENSES = ("reviewer", "sentinel", "simplifier")
VALID_MEMORY_SCOPES = {"user", "project", "local"}

# The review dialect every lens returns (lore/review.md): a tag line in the finding format and the
# round-ledger rule (never repeat a finding an earlier round fixed or closed).
TAG_LINE = "TAG: Important | Nit | Pre-existing"
LEDGER_PATH = ".workspace/shared/diffs/<ref>-rounds.md"


def agent_files() -> list[Path]:
    return sorted(AGENTS.glob("*.md"))


def agent_tools(path: Path) -> set[str]:
    fields, _ = read_frontmatter(path)
    return {t.strip() for t in fields["tools"].split(",") if t.strip()}


class AgentDefinitionTests(unittest.TestCase):
    def test_at_least_the_review_lenses_exist(self) -> None:
        names = {p.stem for p in agent_files()}
        self.assertTrue({"reviewer", "sentinel", "simplifier", "verifier"} <= names,
                        f"core review agents missing; found {names}")

    def test_every_agent_has_required_frontmatter(self) -> None:
        for path in agent_files():
            with self.subTest(agent=path.name):
                fields, body = read_frontmatter(path)
                missing = REQUIRED_FIELDS - set(fields)
                self.assertFalse(missing, f"{path.name} missing fields: {missing}")
                self.assertTrue(body, f"{path.name} has an empty body")

    def test_name_matches_filename(self) -> None:
        for path in agent_files():
            with self.subTest(agent=path.name):
                fields, _ = read_frontmatter(path)
                self.assertEqual(fields["name"], path.stem,
                                 "agent `name` must match its filename so `magician:<name>` resolves")

    def test_description_is_useful_for_routing(self) -> None:
        """The description is what the model reads to decide whether to spawn the agent; an empty
        or one-word description makes the agent effectively un-routable."""
        for path in agent_files():
            with self.subTest(agent=path.name):
                fields, _ = read_frontmatter(path)
                desc = fields["description"]
                self.assertGreaterEqual(len(desc), 30, "description too short to route on")
                self.assertLessEqual(len(desc), 1024, "description implausibly long")

    def test_tools_are_a_known_least_privilege_set(self) -> None:
        for path in agent_files():
            with self.subTest(agent=path.name):
                tools = agent_tools(path)
                self.assertTrue(tools, f"{path.name} declares no tools")
                for tool in tools:
                    self.assertNotIn(tool, FORBIDDEN_TOOLS,
                                     f"{path.name} requests forbidden tool {tool!r}")
                    if tool.startswith("mcp__"):
                        self.assertNotIn("*", tool, f"{path.name} requests a wildcard MCP grant")
                        continue
                    if tool in KG_READ_GRANTS:
                        continue
                    self.assertIn(tool, VALID_TOOLS, f"{path.name} requests unknown tool {tool!r}")

    def test_tools_stay_within_each_agents_ceiling(self) -> None:
        """Read-only unless the agent is a named exception in MAX_TOOLS. A new agent that asks
        for Bash/Edit/Write fails here until the exception is added on purpose."""
        for path in agent_files():
            with self.subTest(agent=path.name):
                ceiling = MAX_TOOLS.get(path.stem, READ_ONLY)
                extra = {t for t in agent_tools(path) if not t.startswith("mcp__")} - ceiling
                self.assertFalse(extra, f"{path.name} exceeds its tool ceiling with {sorted(extra)}")

    def test_read_only_review_agents_cannot_write(self) -> None:
        """A review lens that can Write/Edit could 'fix' code mid-review, and Bash can write files
        too — review agents must be read-only so their findings stay observations, not silent
        mutations."""
        for name in REVIEW_LENSES:
            path = AGENTS / f"{name}.md"
            with self.subTest(agent=name):
                self.assertTrue(path.exists(), f"review lens {name} is missing")
                tools = agent_tools(path)
                for tool in ("Write", "Edit", "Bash", "*"):
                    self.assertNotIn(tool, tools, f"review lens {name} must not have {tool}")
                shell = {t for t in tools if t.startswith("Bash")}
                self.assertFalse(shell - KG_READ_GRANTS,
                                 f"review lens {name} may run only the kg read commands, not {sorted(shell - KG_READ_GRANTS)}")

    def test_lenses_locate_with_kg_and_carry_the_obstacles_pointer(self) -> None:
        """Every review lens holds the kg read grants and says how to use them (locate with kg, read the
        lines it names, grep only to confirm); every agent returns the canonical Obstacles block from
        lore/obstacles.md by pointer (field names inline) instead of pasting it."""
        for name in REVIEW_LENSES:
            path = AGENTS / f"{name}.md"
            with self.subTest(agent=name):
                self.assertTrue(KG_READ_GRANTS <= agent_tools(path), f"{name} lacks the kg read grants")
                _, body = read_frontmatter(path)
                self.assertIn("grep only to confirm", body.lower())
        for path in agent_files():
            with self.subTest(agent=path.stem):
                _, body = read_frontmatter(path)
                self.assertIn("return the Obstacles block from lore/obstacles.md", body)
                for field in ("STATUS", "OBSTACLE", "BLOCKER", "SEVERITY", "WORKAROUND", "RECURRENCE", "SCOPE", "NEXT"):
                    self.assertIn(field, body, f"{path.stem}: Obstacles pointer lacks {field}")
                self.assertNotRegex(body, r"(?m)^STATUS: DEGRADED \| BLOCKED$",
                                    f"{path.stem} still pastes the Obstacles block")

    def test_write_capable_agents_document_why(self) -> None:
        """An agent that keeps write tools must say why in its own body, and bound them, so the
        exception is visible to anyone reading the agent rather than only to this test."""
        fixer = AGENTS / "fixer.md"
        _, body = read_frontmatter(fixer)
        lowered = body.lower()
        self.assertIn("why this agent has write tools", lowered)
        self.assertIn("never touch tests", lowered)
        self.assertIn("acceptance check", lowered)

        _, gate_body = read_frontmatter(AGENTS / "gatekeeper.md")
        self.assertIn("you do not write code", gate_body.lower(),
                      "gatekeeper keeps Bash only to run gates; its body must say it writes no code")

    def test_review_lenses_speak_the_review_dialect(self) -> None:
        """Every lens tags each finding Important / Nit / Pre-existing next to its severity, keeps
        `file:line` in the format, and reads the round ledger when the spawn prompt names it, so a
        finding closed in an earlier remediation round is never repeated (lore/review.md)."""
        for name in REVIEW_LENSES:
            path = AGENTS / f"{name}.md"
            with self.subTest(agent=name):
                _, body = read_frontmatter(path)
                self.assertIn(TAG_LINE, body, f"{name}: finding format lacks the tag line")
                self.assertRegex(body, r"(?m)^FILE: \S*:line", f"{name}: finding format lacks file:line")
                self.assertIn(LEDGER_PATH, body, f"{name}: no round-ledger rule")
                self.assertIn("fixed or closed", body, f"{name}: must never repeat a fixed/closed finding")

    def test_memory_scope_is_declared_only_where_intended(self) -> None:
        """`memory:` persists a MEMORY.md per agent across runs. Only the three finder lenses carry it,
        at project scope, and each body states the two-recurrence rule, the Obstacles NEXT route for
        a lint/CLAUDE.md proposal, and that memory's write tools never touch code. Any other agent
        gaining `memory:` is a deliberate change made here."""
        for path in agent_files():
            fields, body = read_frontmatter(path)
            with self.subTest(agent=path.stem):
                if path.stem in MEMORY_LENSES:
                    self.assertEqual(fields.get("memory"), "project", f"{path.stem} must use memory: project")
                    lowered = body.lower()
                    self.assertIn("recurs twice", lowered, f"{path.stem}: missing the two-recurrence rule")
                    self.assertIn("`next` field", lowered, f"{path.stem}: must propose rules via Obstacles NEXT")
                    self.assertIn("findings stay observations", lowered, f"{path.stem}: memory must not imply code edits")
                    self.assertIn(f".claude/agent-memory/{path.stem}/", body)
                else:
                    self.assertNotIn("memory", fields, f"{path.stem} must not declare memory")
                if "memory" in fields:
                    self.assertIn(fields["memory"], VALID_MEMORY_SCOPES)

    def test_worktree_isolation_is_per_call_not_frontmatter(self) -> None:
        """`isolation: worktree` branches from the default branch, not the caller's HEAD, so it is
        wrong for a sequential in-place fix on a feature branch. No agent pins it in frontmatter;
        the fixer documents the per-call mode (branch from the review branch, return BRANCH) and
        /scrutinize passes `isolation` on the call only for parallel fixes."""
        for path in agent_files():
            fields, _ = read_frontmatter(path)
            with self.subTest(agent=path.stem):
                self.assertNotIn("isolation", fields, f"{path.stem} pins isolation in frontmatter")
        _, body = read_frontmatter(AGENTS / "fixer.md")
        self.assertIn('isolation: "worktree"', body)
        self.assertIn("git checkout -b fix/<finding-id> <review-branch>", body)
        self.assertRegex(body, r"(?m)^BRANCH: in-place \| fix/<finding-id>$")
        scrutinize = (SKILLS / "scrutinize" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn('isolation: "worktree"', scrutinize)
        self.assertIn("runs in place", scrutinize)

    def test_model_is_a_valid_value(self) -> None:
        for path in agent_files():
            with self.subTest(agent=path.name):
                fields, _ = read_frontmatter(path)
                model = fields["model"]
                ok = model in VALID_MODEL_ALIASES or model.startswith("claude-")
                self.assertTrue(ok, f"{path.name} has unknown model {model!r}")

    def test_no_prior_conversation_assumption(self) -> None:
        """Every magician agent runs with a fresh context. Each body must state that it does not
        see the parent conversation and must declare what to do when context is missing, so a
        spawned agent never silently guesses. This is the plugin's subagent-context contract."""
        for path in agent_files():
            with self.subTest(agent=path.name):
                _, body = read_frontmatter(path)
                lowered = body.lower()
                self.assertTrue(
                    "needs_context" in lowered or "do not see" in lowered
                    or "does not see" in lowered or "no prior conversation" in lowered,
                    f"{path.name} does not declare the fresh-context contract",
                )

    def test_agents_are_wired_to_be_spawned(self) -> None:
        """The plugin's headline promise is that it can *spin up* its agents. The orchestration
        skills dispatch subagents by `magician:<name>` via the Task tool, so two invariants must
        hold deterministically (behavioral spawn is model-discretionary and lives in the eval tier,
        not here): (1) every `magician:<name>` a skill references resolves to a real agent or skill
        — a dangling one fails at runtime with "unknown subagent_type"; and (2) the parallel-review
        skill actually dispatches the review-lens agents, which is the reliable proof they are
        registered and dispatchable."""
        agents = {p.stem for p in agent_files()}
        skills = {p.parent.name for p in SKILLS.glob("*/SKILL.md")}
        # Output styles are also addressed as `magician:<name>` (`/output-style magician:ste`), so
        # they count as resolvable references too.
        styles = {p.stem for p in (ROOT / "output-styles").glob("*.md")}
        known = agents | skills | styles
        ref = re.compile(r"magician:([a-z0-9][\w-]*)")

        dangling: dict[str, list[str]] = {}
        for skill in sorted(SKILLS.glob("*/SKILL.md")):
            for name in set(ref.findall(skill.read_text(encoding="utf-8"))):
                if name not in known:
                    dangling.setdefault(f"magician:{name}", []).append(skill.parent.name)
        self.assertFalse(dangling,
                         f"skills reference non-existent magician:<name> dispatch targets: {dangling}")

        scrutinize = SKILLS / "scrutinize" / "SKILL.md"
        self.assertTrue(scrutinize.exists(), "parallel-review skill 'scrutinize' is missing")
        dispatched = {n for n in ref.findall(scrutinize.read_text(encoding="utf-8")) if n in agents}
        self.assertTrue({"reviewer", "sentinel", "simplifier"} <= dispatched,
                        f"scrutinize must dispatch the review-lens agents via Task; found {dispatched}")


if __name__ == "__main__":
    unittest.main()
