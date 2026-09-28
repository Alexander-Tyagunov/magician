"""Hook-wiring contract for the Claude-side plugin.

Every hook Claude Code fires must resolve to a real, executable script, be attached to a
valid lifecycle event, and use a well-formed matcher. A broken hook wire is silent in
production — the event simply never runs — so this gate makes the wiring itself testable.

The wiring is pinned exactly: each command is the quoted literal form
`"${CLAUDE_PLUGIN_ROOT}"/scripts/<name>.sh` (no arguments, no other paths), and the set of
events, matchers and scripts is fixed, so a removed hook cannot come back unnoticed.

These tests read only declarative config + the filesystem; they never execute a hook.
"""
from __future__ import annotations

import json
import re
import stat
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "hooks" / "hooks.json"
MONITORS = ROOT / "monitors" / "monitors.json"

# The lifecycle events Claude Code exposes to plugins (per docs.claude.com/en/docs/claude-code/hooks).
# Anything outside this set is a typo that would leave the hook permanently dormant.
VALID_EVENTS = {
    # per-session
    "SessionStart", "SessionEnd", "Setup",
    # per-turn
    "UserPromptSubmit", "UserPromptExpansion", "Stop", "StopFailure", "TeammateIdle",
    # per-tool-call
    "PreToolUse", "PermissionRequest", "PermissionDenied",
    "PostToolUse", "PostToolUseFailure", "PostToolBatch",
    # subagent / task
    "SubagentStart", "SubagentStop", "TaskCreated", "TaskCompleted",
    # async / monitoring
    "Notification", "MessageDisplay", "InstructionsLoaded", "ConfigChange",
    "CwdChanged", "DirectoryAdded", "FileChanged", "WorktreeCreate", "WorktreeRemove",
    "PreCompact", "PostCompact", "PreModelSwitch", "PostModelSwitch",
    # mcp
    "Elicitation", "ElicitationResult",
}

# Events whose groups may carry a `matcher` (tool name, notification type, session source).
MATCHER_EVENTS = {"PreToolUse", "PostToolUse", "Notification", "SessionStart"}

# The only accepted command form: quoted plugin root, literal scripts/<name>.sh path, no arguments.
COMMAND_RE = re.compile(r'^"\$\{CLAUDE_PLUGIN_ROOT\}"/scripts/([a-z0-9-]+\.sh)$')

# The complete wiring: event -> [(matcher or None, [(script, extra hook keys)])], in order.
EXPECTED_WIRING = {
    "SessionStart": [
        (None, [("session-start.sh", {}), ("userconfig-env.sh", {"timeout": 10})]),
        ("compact", [("compact-context.sh", {})]),
    ],
    "UserPromptSubmit": [(None, [("pattern-detect.sh", {})])],
    "PreToolUse": [("Bash|PowerShell", [("destructive-guard.sh", {})])],
    "PostToolUse": [("Write|Edit", [("format.sh", {})])],
    "Notification": [("agent_completed|agent_needs_input", [("notify.sh", {})])],
    "Stop": [(None, [("chronicle-stop.sh", {"async": True})])],
}

REMOVED_SCRIPTS = ("access-tracker.sh", "agent-lifecycle.sh", "worktree-init.sh",
                   "pre-compact.sh", "jira-mcp-nudge.sh", "kg-nudge.sh")
REMOVED_EVENTS = ("PreCompact", "SubagentStart", "SubagentStop", "WorktreeCreate")

ALLOWED_HOOK_KEYS = {"type", "command", "timeout", "async"}


def _script_of(command: str) -> str | None:
    m = COMMAND_RE.match(command)
    return m.group(1) if m else None


def _assert_executable(test: unittest.TestCase, script: Path) -> None:
    test.assertTrue(script.is_file(), f"missing hook script: {script.relative_to(ROOT)}")
    mode = script.stat().st_mode
    test.assertTrue(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH),
                    f"hook script not executable: {script.relative_to(ROOT)}")


class HookWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(HOOKS.read_text(encoding="utf-8"))

    def _hooks(self):
        for event, groups in self.config["hooks"].items():
            for group in groups:
                for hook in group["hooks"]:
                    yield event, group, hook

    def test_hooks_file_is_well_formed(self) -> None:
        self.assertEqual(set(self.config), {"hooks"})
        self.assertIsInstance(self.config["hooks"], dict)
        self.assertTrue(self.config["hooks"], "no hooks declared")

    def test_every_event_is_a_real_lifecycle_event(self) -> None:
        for event in self.config["hooks"]:
            with self.subTest(event=event):
                self.assertIn(event, VALID_EVENTS)

    def test_every_command_is_the_quoted_literal_script_form(self) -> None:
        for event, _group, hook in self._hooks():
            with self.subTest(event=event, command=hook.get("command")):
                self.assertEqual(hook["type"], "command")
                self.assertIsNotNone(
                    _script_of(hook["command"]),
                    'command must be exactly "${CLAUDE_PLUGIN_ROOT}"/scripts/<name>.sh')

    def test_every_command_resolves_to_an_executable_script(self) -> None:
        for event, _group, hook in self._hooks():
            name = _script_of(hook["command"])
            with self.subTest(event=event, script=name):
                self.assertIsNotNone(name)
                _assert_executable(self, ROOT / "scripts" / name)

    def test_hook_entries_use_only_known_keys(self) -> None:
        for event, group, hook in self._hooks():
            with self.subTest(event=event, command=hook["command"]):
                self.assertLessEqual(set(hook), ALLOWED_HOOK_KEYS)
                self.assertLessEqual(set(group), {"matcher", "hooks"})

    def test_wiring_is_exactly_the_contract(self) -> None:
        actual = {}
        for event, groups in self.config["hooks"].items():
            actual[event] = [
                (group.get("matcher"),
                 [(_script_of(h["command"]),
                   {k: v for k, v in h.items() if k not in ("type", "command")})
                  for h in group["hooks"]])
                for group in groups
            ]
        self.assertEqual(actual, EXPECTED_WIRING)

    def test_matchers_are_valid_regexes_on_matcher_events(self) -> None:
        for event, groups in self.config["hooks"].items():
            for group in groups:
                matcher = group.get("matcher")
                if matcher is None:
                    continue
                with self.subTest(event=event, matcher=matcher):
                    self.assertIn(event, MATCHER_EVENTS,
                                  f"{event} declares a matcher but does not support one")
                    try:
                        re.compile(matcher)
                    except re.error as exc:
                        self.fail(f"invalid matcher regex {matcher!r}: {exc}")

    def test_destructive_guard_is_wired_before_bash(self) -> None:
        """The catastrophic-command gate must be a PreToolUse(Bash) hook — if it moved to
        PostToolUse or lost its Bash matcher it would inspect commands only after they ran."""
        pre = self.config["hooks"].get("PreToolUse", [])
        guarded = [g for g in pre if any(_script_of(h["command"]) == "destructive-guard.sh"
                                         for h in g["hooks"])]
        self.assertTrue(guarded, "destructive-guard.sh is not wired into PreToolUse")
        for group in guarded:
            self.assertTrue(re.fullmatch(group["matcher"], "Bash"))
            self.assertTrue(re.fullmatch(group["matcher"], "PowerShell"))

    def test_notify_fires_only_for_agent_notifications(self) -> None:
        groups = self.config["hooks"]["Notification"]
        self.assertEqual(len(groups), 1)
        matcher = groups[0]["matcher"]
        for kind in ("agent_completed", "agent_needs_input"):
            self.assertTrue(re.fullmatch(matcher, kind), kind)
        for kind in ("permission_prompt", "idle_prompt", "auth_success", "elicitation_dialog"):
            self.assertIsNone(re.fullmatch(matcher, kind), kind)

    def test_only_the_chronicle_hook_is_async(self) -> None:
        for event, _group, hook in self._hooks():
            with self.subTest(command=hook["command"]):
                if _script_of(hook["command"]) == "chronicle-stop.sh":
                    self.assertEqual(event, "Stop")
                    self.assertIs(hook.get("async"), True)
                else:
                    self.assertNotIn("async", hook)

    def test_userconfig_bridge_has_a_short_timeout(self) -> None:
        found = [(e, h) for e, _g, h in self._hooks() if _script_of(h["command"]) == "userconfig-env.sh"]
        self.assertEqual(len(found), 1)
        event, hook = found[0]
        self.assertEqual(event, "SessionStart")
        self.assertEqual(hook.get("timeout"), 10)

    def test_removed_hooks_and_events_are_absent(self) -> None:
        raw = HOOKS.read_text(encoding="utf-8")
        for event in REMOVED_EVENTS:
            with self.subTest(event=event):
                self.assertNotIn(event, self.config["hooks"])
        for name in REMOVED_SCRIPTS:
            with self.subTest(script=name):
                self.assertNotIn(name, raw)
                self.assertFalse((ROOT / "scripts" / name).exists(), f"scripts/{name} still shipped")


class MonitorWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.monitors = json.loads(MONITORS.read_text(encoding="utf-8"))

    def test_monitors_use_the_quoted_literal_script_form(self) -> None:
        self.assertIsInstance(self.monitors, list)
        for mon in self.monitors:
            with self.subTest(monitor=mon.get("name")):
                name = _script_of(mon["command"])
                self.assertIsNotNone(name)
                _assert_executable(self, ROOT / "scripts" / name)

    def test_ci_watch_starts_with_the_deploy_skill(self) -> None:
        (mon,) = [m for m in self.monitors if m["name"] == "ci-watch"]
        self.assertEqual(mon["when"], "on-skill-invoke:deploy")
        self.assertTrue((ROOT / "skills" / "deploy" / "SKILL.md").is_file())
        desc = mon["description"]
        self.assertIn("current branch", desc)
        self.assertNotRegex(desc.lower(), r"\bpings? claude\b")


if __name__ == "__main__":
    unittest.main()
