"""Hook-wiring contract for the Claude-side plugin.

Every hook Claude Code fires must resolve to a real, executable script, be attached to a
valid lifecycle event, and use a well-formed matcher. A broken hook wire is silent in
production — the event simply never runs — so this gate makes the wiring itself testable.

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

# Events that key off a tool name accept a `matcher`; lifecycle-only events do not need one.
MATCHER_EVENTS = {"PreToolUse", "PostToolUse"}


class HookWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(HOOKS.read_text(encoding="utf-8"))

    def test_hooks_file_is_well_formed(self) -> None:
        self.assertIn("hooks", self.config)
        self.assertIsInstance(self.config["hooks"], dict)
        self.assertTrue(self.config["hooks"], "no hooks declared")

    def test_every_event_is_a_real_lifecycle_event(self) -> None:
        for event in self.config["hooks"]:
            with self.subTest(event=event):
                self.assertIn(event, VALID_EVENTS)

    def test_every_command_resolves_to_an_executable_script(self) -> None:
        for event, groups in self.config["hooks"].items():
            for group in groups:
                for hook in group["hooks"]:
                    with self.subTest(event=event, command=hook.get("command")):
                        self.assertEqual(hook["type"], "command")
                        command = hook["command"]
                        self.assertIn("${CLAUDE_PLUGIN_ROOT}", command)
                        rel = command.split("${CLAUDE_PLUGIN_ROOT}/", 1)[1].split()[0]
                        script = ROOT / rel
                        self.assertTrue(script.is_file(), f"missing hook script: {rel}")
                        mode = script.stat().st_mode
                        self.assertTrue(
                            mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH),
                            f"hook script not executable: {rel}",
                        )

    def test_tool_matchers_are_valid_regexes(self) -> None:
        for event, groups in self.config["hooks"].items():
            for group in groups:
                matcher = group.get("matcher")
                if matcher is None:
                    continue
                with self.subTest(event=event, matcher=matcher):
                    self.assertIn(event, MATCHER_EVENTS,
                                  f"{event} declares a matcher but is not a tool event")
                    try:
                        re.compile(matcher)
                    except re.error as exc:
                        self.fail(f"invalid matcher regex {matcher!r}: {exc}")

    def test_destructive_guard_is_wired_before_bash(self) -> None:
        """The catastrophic-command gate must be a PreToolUse(Bash) hook — if it moved to
        PostToolUse or lost its Bash matcher it would inspect commands only after they ran."""
        pre = self.config["hooks"].get("PreToolUse", [])
        guarded = [
            g for g in pre
            if any("destructive-guard.sh" in h["command"] for h in g["hooks"])
        ]
        self.assertTrue(guarded, "destructive-guard.sh is not wired into PreToolUse")
        for group in guarded:
            self.assertIn("Bash", group["matcher"])

    def test_compaction_capture_is_wired(self) -> None:
        pre_compact = self.config["hooks"].get("PreCompact", [])
        commands = [h["command"] for g in pre_compact for h in g["hooks"]]
        self.assertTrue(any("pre-compact.sh" in c for c in commands),
                        "pre-compact.sh is not wired into PreCompact")

    def test_subagent_lifecycle_is_wired_both_ends(self) -> None:
        for event in ("SubagentStart", "SubagentStop"):
            with self.subTest(event=event):
                groups = self.config["hooks"].get(event, [])
                commands = [h["command"] for g in groups for h in g["hooks"]]
                self.assertTrue(any("agent-lifecycle.sh" in c for c in commands),
                                f"agent-lifecycle.sh not wired into {event}")


if __name__ == "__main__":
    unittest.main()
