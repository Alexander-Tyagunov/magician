#!/usr/bin/env python3
"""Codex-only destructive command guard.

Consumes a Codex ``PreToolUse`` JSON event on stdin.  A known catastrophic Bash
command is denied with exit 2 and non-empty stderr; unrelated, incomplete, or
malformed input fails open so a hook defect cannot disable the shell.

This is defense in depth, not a shell sandbox.  It inspects only the command in a
new Bash tool call.  In particular, Codex cannot currently run PreToolUse again
for bytes later sent to an existing process with ``write_stdin``.  The matcher is
therefore deliberately conservative and must be layered with Codex sandboxing,
approvals, and user review.
"""
from __future__ import annotations

import json
import fnmatch
import posixpath
import re
import shlex
import sys
from typing import Iterable


ROOTS_ALL = {
    "Applications", "Library", "System", "Users", "Volumes", "bin", "boot",
    "cores", "dev", "etc", "home", "lib", "lib32", "lib64", "libx32",
    "media", "mnt", "opt", "private", "proc", "root", "run", "sbin",
    "srv", "sys", "usr", "var",
}
ROOTS_SYSTEM = {
    "Library", "System", "bin", "boot", "dev", "etc", "lib", "lib32",
    "lib64", "libx32", "proc", "root", "sbin", "sys", "usr",
}
CRITICAL_FILES = {
    "/etc/fstab", "/etc/group", "/etc/hosts", "/etc/master.passwd",
    "/etc/passwd", "/etc/shadow", "/etc/sudoers",
}
BLOCK_DEVICE = re.compile(
    r"^/dev/(?:sd[a-z]\d*|nvme\d+(?:n\d+)?(?:p\d+)?|hd[a-z]\d*|vd[a-z]\d*|"
    r"xvd[a-z]\d*|mmcblk\d+(?:p\d+)?|r?disk\d+(?:s\d+)?|mapper/.+|loop\d+)$"
)
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$", re.S)
INTERPRETERS = {
    "bash", "dash", "fish", "ksh", "node", "perl", "python", "python2",
    "python3", "ruby", "sh", "zsh",
}
DOWNLOADERS = {"curl", "fetch", "wget"}
SHELLS = {"bash", "dash", "ksh", "sh", "zsh"}


def _name(value: str) -> str:
    return value.rsplit("/", 1)[-1].lower()


def _tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars="|&;<>()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def _segments(tokens: Iterable[str]) -> list[list[str]]:
    result: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token and all(char in "|&;" for char in token):
            if current:
                result.append(current)
                current = []
        else:
            current.append(token)
    if current:
        result.append(current)
    return result


def _substitutions(command: str) -> tuple[list[str], str]:
    """Return executable command substitutions and a copy with them blanked.

    Single-quoted text is inert.  Dollar substitutions remain executable inside
    double quotes, as do legacy backticks.  The bounded recursive caller handles
    nested payloads without trying to implement an entire shell parser.
    """
    found: list[str] = []
    chars = list(command)
    i = 0
    quote = ""
    while i < len(command):
        char = command[i]
        if char == "\\":
            i += 2
            continue
        if char == "'" and quote != '"':
            quote = "" if quote == "'" else "'"
            i += 1
            continue
        if char == '"' and quote != "'":
            quote = "" if quote == '"' else '"'
            i += 1
            continue
        if quote != "'" and command.startswith("$(", i):
            start = i
            depth = 1
            j = i + 2
            inner_quote = ""
            while j < len(command) and depth:
                c = command[j]
                if c == "\\":
                    j += 2
                    continue
                if c in "'\"":
                    inner_quote = "" if inner_quote == c else (c if not inner_quote else inner_quote)
                elif not inner_quote and command.startswith("$(", j):
                    depth += 1
                    j += 1
                elif not inner_quote and c == ")":
                    depth -= 1
                j += 1
            if depth == 0:
                found.append(command[i + 2:j - 1])
                chars[start:j] = " " * (j - start)
                i = j
                continue
        if quote != "'" and char == "`":
            j = i + 1
            while j < len(command):
                if command[j] == "\\":
                    j += 2
                    continue
                if command[j] == "`":
                    break
                j += 1
            if j < len(command):
                found.append(command[i + 1:j])
                chars[i:j + 1] = " " * (j + 1 - i)
                i = j + 1
                continue
        i += 1
    return found, "".join(chars)


def _unwrap(tokens: list[str]) -> list[str]:
    values = list(tokens)
    while values:
        while values and ASSIGNMENT.match(values[0]):
            values.pop(0)
        if not values:
            return values
        command = _name(values[0])
        if command in {"command", "builtin", "exec", "nohup"}:
            values.pop(0)
            while values and values[0].startswith("-"):
                values.pop(0)
            continue
        if command in {"sudo", "doas"}:
            values.pop(0)
            options_with_value = {"-C", "-D", "-g", "-h", "-p", "-R", "-T", "-t", "-u"}
            long_options_with_value = {
                "--chdir", "--close-from", "--group", "--host", "--prompt",
                "--role", "--type", "--user",
            }
            while values and values[0].startswith("-"):
                option = values.pop(0)
                if (option in options_with_value or option in long_options_with_value) and values:
                    values.pop(0)
            continue
        if command == "env":
            values.pop(0)
            options_with_value = {"-C", "-S", "-u", "--chdir", "--split-string", "--unset"}
            while values and (values[0].startswith("-") or ASSIGNMENT.match(values[0])):
                option = values.pop(0)
                if option in options_with_value and values:
                    values.pop(0)
            continue
        if command == "timeout":
            values.pop(0)
            options_with_value = {"-k", "-s", "--kill-after", "--signal"}
            while values and values[0].startswith("-"):
                option = values.pop(0)
                if option in options_with_value and values:
                    values.pop(0)
            if values:  # duration
                values.pop(0)
            continue
        if command == "nice":
            values.pop(0)
            if values and values[0] in {"-n", "--adjustment"}:
                values.pop(0)
                if values:
                    values.pop(0)
            elif values and re.match(r"^-\d+$", values[0]):
                values.pop(0)
            continue
        break
    return values


def _target(value: str) -> str:
    value = value.strip()
    value = re.sub(
        r"^(?:\$HOME|\$\{HOME(?:[:?+\-=][^}]*)?\}|~)(?=/|$)",
        "__HOME__",
        value,
    )
    if value.startswith("/") or value.startswith("__HOME__"):
        prefix = "__HOME__" if value.startswith("__HOME__") else ""
        if prefix:
            value = value[len(prefix):] or "/"
        value = "/" + value.lstrip("/")
        value = posixpath.normpath(value)
        value = prefix + ("" if value == "/" and prefix else value)
    return value.rstrip("/") or "/"


def _root_pattern(value: str) -> bool:
    """Recognize common shell patterns that expand to a top-level root."""
    alternatives = [value]
    brace = re.fullmatch(r"\{([^{}]+)\}", value)
    if brace:
        alternatives = brace.group(1).split(",")
    return any(
        fnmatch.fnmatchcase(root, pattern)
        for pattern in alternatives
        for root in ROOTS_ALL
    )


def _catastrophic_target(value: str) -> bool:
    value = _target(value)
    if value == "/" or value in {"__HOME__", "__HOME__/*"}:
        return True
    if not value.startswith("/"):
        return False
    parts = value[1:].split("/")
    top = parts[0]
    if len(parts) == 1 and _root_pattern(top):
        return True
    return top in ROOTS_SYSTEM


def _block_device(value: str) -> bool:
    return BLOCK_DEVICE.match(_target(value)) is not None


def _flags(arguments: Iterable[str]) -> tuple[set[str], set[str]]:
    short: set[str] = set()
    long: set[str] = set()
    for value in arguments:
        if value.startswith("--"):
            long.add(value.split("=", 1)[0])
        elif re.match(r"^-[A-Za-z]+$", value):
            short.update(value[1:])
    return short, long


def _git_clean(tokens: list[str]) -> bool:
    if not tokens or _name(tokens[0]) != "git":
        return False
    i = 1
    options_with_value = {"-C", "-c", "--exec-path", "--git-dir", "--namespace", "--work-tree"}
    while i < len(tokens):
        value = tokens[i]
        if value == "clean":
            short, long = _flags(tokens[i + 1:])
            return "f" in short and "x" in short or "--force" in long and "x" in short
        if value in options_with_value:
            i += 2
        elif value.startswith("-"):
            i += 1
        else:
            return False
    return False


def _segment_reason(raw: list[str]) -> str | None:
    tokens = _unwrap(raw)
    if not tokens:
        return None
    command = _name(tokens[0])
    arguments = tokens[1:]
    short, long = _flags(arguments)

    if command == "rm":
        recursive = bool({"r", "R"} & short) or "--recursive" in long
        force = "f" in short or "--force" in long
        targets = [value for value in arguments if not value.startswith("-")]
        if "--no-preserve-root" in long and any(_catastrophic_target(value) for value in targets):
            return "rm --no-preserve-root defeats the root-deletion failsafe"
        if recursive and force and any(_catastrophic_target(value) for value in targets):
            return "recursive forced removal of a system or home root"

    if command == "find" and any(_catastrophic_target(value) for value in arguments):
        destructive_exec = any(
            value in {"-exec", "-execdir"}
            and index + 1 < len(arguments)
            and _name(arguments[index + 1]) in {"rm", "sh", "bash", "zsh"}
            for index, value in enumerate(arguments)
        )
        if "-delete" in arguments or destructive_exec:
            return "destructive find on a system or home root"

    if command in {"chmod", "chown", "chgrp"}:
        recursive = "R" in short or "--recursive" in long
        if recursive and any(_catastrophic_target(value) for value in arguments):
            return "recursive permission or ownership change on a protected root"

    if command == "dd":
        for value in arguments:
            if value.startswith("of=") and _block_device(value[3:]):
                return "dd writing to a block device"

    if command.startswith("mkfs") and any(_block_device(value) for value in arguments):
        return "formatting a block device"
    if command in {"wipefs", "blkdiscard", "shred", "sfdisk"}:
        if any(_block_device(value) for value in arguments):
            return f"{command} operating on a block device"
    if command == "sgdisk" and ({"Z"} & short or {"--zap", "--zap-all"} & long):
        return "sgdisk destroying a partition table"
    if command == "diskutil" and any(
        re.match(r"^(?:eraseDisk|eraseVolume|zeroDisk|randomDisk|reformat|secureErase)$", value, re.I)
        for value in arguments
    ):
        return "diskutil destructive disk operation"

    for index, value in enumerate(tokens[:-1]):
        if ">" in value and set(value) <= {">"}:
            destination = _target(tokens[index + 1])
            if destination in CRITICAL_FILES or _block_device(destination):
                return "redirecting output to a critical file or block device"
    if command == "tee":
        destinations = [value for value in arguments if not value.startswith("-")]
        if any(_target(value) in CRITICAL_FILES or _block_device(value) for value in destinations):
            return "tee writing to a critical file or block device"

    if _git_clean(tokens):
        return "git clean -x irreversibly deletes ignored and untracked files"

    if command in SHELLS:
        for index, value in enumerate(arguments[:-1]):
            if value.startswith("-") and "c" in value[1:]:
                payload_index = index + 1
                if arguments[payload_index] == "--" and payload_index + 1 < len(arguments):
                    payload_index += 1
                reason = check_bash(arguments[payload_index], depth=1)
                if reason:
                    return reason
    return None


def _pipeline_reason(tokens: list[str]) -> str | None:
    chunks: list[list[str]] = []
    operators: list[str] = []
    current: list[str] = []
    for token in tokens:
        if token and all(char in "|&;" for char in token):
            chunks.append(current)
            operators.append(token)
            current = []
        else:
            current.append(token)
    chunks.append(current)
    for operator, left, right in zip(operators, chunks, chunks[1:]):
        if operator != "|":
            continue
        left = _unwrap(left)
        right = _unwrap(right)
        if not left or not right:
            continue
        left_name = _name(left[0])
        right_name = _name(right[0])
        if left_name in DOWNLOADERS and right_name in INTERPRETERS:
            if right_name in {"python", "python2", "python3"} and right[1:] == ["-m", "json.tool"]:
                continue
            return "piping a network download directly into an interpreter"
        short, long = _flags(left[1:])
        if left_name == "base64" and ("d" in short or "--decode" in long) and right_name in SHELLS:
            return "decoding base64 directly into a shell"
    return None


def check_bash(command: str, depth: int = 0) -> str | None:
    if not command.strip() or depth > 5:
        return None
    substitutions, outer = _substitutions(command)
    try:
        outer_tokens = _tokens(outer)
    except ValueError:
        return None
    outer_segments = _segments(outer_tokens)
    if substitutions:
        for segment in outer_segments:
            unwrapped = _unwrap(segment)
            if not unwrapped or _name(unwrapped[0]) != "rm":
                continue
            short, long = _flags(unwrapped[1:])
            recursive = bool({"r", "R"} & short) or "--recursive" in long
            force = "f" in short or "--force" in long
            if recursive and force:
                return "dynamic target in recursive forced removal"
    first = _unwrap(outer_segments[0]) if outer_segments else []
    if first and _name(first[0]) == "eval":
        for inner in substitutions:
            try:
                inner_segments = _segments(_tokens(inner))
            except ValueError:
                continue
            inner_first = _unwrap(inner_segments[0]) if inner_segments else []
            if inner_first and _name(inner_first[0]) in DOWNLOADERS | {"base64"}:
                return "eval of a network download or decoded payload"
    for inner in substitutions:
        reason = check_bash(inner, depth + 1)
        if reason:
            return "destructive command substitution: " + reason
    tokens = outer_tokens
    fork = [":", "()", "{", ":", "|", ":", "&", "}", ";", ":"]
    if any(tokens[index:index + len(fork)] == fork for index in range(len(tokens) - len(fork) + 1)):
        return "fork bomb"
    segments = outer_segments
    for segment in segments:
        reason = _segment_reason(segment)
        if reason:
            return reason
    return _pipeline_reason(tokens)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (TypeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if payload.get("hook_event_name") != "PreToolUse" or payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return 0
    try:
        reason = check_bash(command)
    except Exception:
        return 0
    if not reason:
        return 0
    sys.stderr.write(
        "[MAGICIAN CODEX HARD-GATE] Refused catastrophic Bash command: " + reason + ".\n"
        "This Codex defense-in-depth check cannot be overridden. Do not retry or obscure the "
        "command; if it is genuinely intended, the human must run it outside the agent.\n"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
