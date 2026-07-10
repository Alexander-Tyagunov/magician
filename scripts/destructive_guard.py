#!/usr/bin/env python3
"""Magician destructive-command hard gate (PreToolUse matcher).

Blocks catastrophic Bash/PowerShell commands UNCONDITIONALLY: on a match it writes a
[MAGICIAN HARD-GATE] message to stderr and exits 2, which stops the tool call BEFORE Claude Code
evaluates permission rules — so the block overrides `allow` rules and fires in every mode. No escape
hatch by design.

HONEST SCOPE (CWE-78): a denylist cannot catch every obfuscation — arbitrary base64/eval/variable
indirection can hide anything. This is a deterministic net for KNOWN catastrophic forms plus common
command wrappers, layered under OS sandboxing, Claude Code auto mode's classifier, and model judgment.
It is NOT a complete sandbox. Within its coverage the block is absolute. It only inspects the command
string; it never executes anything. On its own internal error it fails OPEN (exit 0) so a matcher bug
can never brick the user's shell.
"""
import json
import re
import sys

# --- catastrophic path targets (system + user data) ---------------------------------------------
# Every top-level system/data dir — the dir ITSELF (or /*) is catastrophic to delete/chmod.
_ROOTS_ALL = (r"bin|boot|dev|etc|lib|lib32|lib64|libx32|opt|proc|root|run|sbin|srv|sys|usr|var|"
              r"home|Users|System|Library|Applications|private|Volumes|cores|mnt|media")
# System-critical roots — deleting *inside* these (a subpath) also breaks the OS, so subpaths count.
# Data roots (home, Users, opt, srv, var, Volumes, ...) are intentionally NOT here: deleting a
# subpath like $HOME/project/build or /var/www is normal work and must be allowed.
_ROOTS_SYS = r"bin|boot|dev|etc|lib|lib32|lib64|libx32|proc|root|sbin|sys|usr|System|Library"
# The root itself: / , /* , ~ , $HOME, or a top-level dir (optionally trailing / or /*) — NOT its subpaths.
CAT_EXACT = (r"(?:/|/\*|/\.|~|~/|\$HOME|\$\{HOME\}|\"\$HOME\"|'\$HOME'"
             r"|/(?:" + _ROOTS_ALL + r")(?:/|/\*)?)")
# A subpath under a system-critical root: /usr/local, /etc/nginx, /System/Library, ...
SYS_SUB = r"/(?:" + _ROOTS_SYS + r")/\S+"
# Raw block-device paths (NOT /dev/null|zero|random|tty|stdout|stderr|fd — those are safe sinks/sources).
DEV = r"/dev/(?:sd[a-z]|nvme\d|hd[a-z]|vd[a-z]|xvd[a-z]|mmcblk\d|disk\d|rdisk\d|mapper/\S+|loop\d)"
# Critical system files that must never be truncated/overwritten.
CRIT = r"/etc/(?:passwd|shadow|sudoers|fstab|hosts|group|master\.passwd)"

_WRAP = re.compile(
    r"^(?:sudo|doas|command|builtin|exec|nohup|setsid|time|"
    r"env(?:\s+[A-Za-z_][A-Za-z0-9_]*=\S*)*|"
    r"timeout(?:\s+-?\S+)*|nice(?:\s+-n?\s*-?\d+)?|ionice(?:\s+-\S+)*|"
    r"stdbuf(?:\s+-\S+)*|xargs(?:\s+-\S+)*|chrt(?:\s+-\S+)*|taskset(?:\s+\S+)*)\s+", re.I)


def _strip_wrappers(s):
    """Peel leading process/exec wrappers so `sudo rm -rf /` matches like `rm -rf /`."""
    prev = None
    while prev != s:
        prev = s
        s = _WRAP.sub("", s, count=1)
    return s


def _shorts(seg):
    """Concatenated short-flag letters, e.g. '-rf -x' -> 'rfx'."""
    return "".join(re.findall(r"(?<!\S)-([A-Za-z]+)\b", seg))


def _longs(seg):
    return re.findall(r"--[a-z][a-z-]*", seg)


def _has_target(seg):
    """True if the segment names a catastrophic target: a root itself, or a subpath of a system root.
    Subpaths of home/data roots (e.g. $HOME/project, /var/www) are deliberately NOT catastrophic."""
    return (re.search(r"(?:^|\s)" + CAT_EXACT + r"(?:\s|$)", seg) is not None
            or re.search(r"(?:^|\s)" + SYS_SUB, seg) is not None)


def check_bash(cmd, _depth=0):
    """Return a reason string if the Bash command is catastrophic, else None."""
    s = re.sub(r"\s+", " ", cmd).strip()
    if not s:
        return None
    whole = _strip_wrappers(s)

    # Recurse into `sh -c '...'` / `bash -lc "..."` payloads so a wrapped catastrophic command is
    # caught (e.g. `bash -c 'rm -rf /'`). Bounded depth so a crafted self-nesting string can't loop.
    if _depth < 4:
        for m in re.finditer(r"\b(?:sh|bash|zsh|ksh|dash)\s+-[A-Za-z]*c\b\s+('([^']*)'|\"([^\"]*)\")",
                             whole):
            inner = m.group(2) if m.group(2) is not None else (m.group(3) or "")
            if inner:
                r = check_bash(inner, _depth + 1)
                if r:
                    return r

    # For the whole-string obfuscation/redirection rules, blank out quoted spans first so a command
    # that merely MENTIONS a dangerous string in an argument (e.g. `git commit -m "curl x | bash"`)
    # doesn't false-trigger. Real execution forms (curl|bash, :(){...}, > /dev/sda) are unquoted.
    whole_nq = re.sub(r"'[^']*'", " ", whole)
    whole_nq = re.sub(r'"[^"]*"', " ", whole_nq)
    # For command-substitution detection ($(...) runs even inside DOUBLE quotes), strip only
    # single-quoted spans — keep double-quoted so `eval "$(curl ...)"` is still caught.
    whole_dq = re.sub(r"'[^']*'", " ", whole)

    # per-subcommand segments (split on shell operators), each wrapper-stripped
    segs = [_strip_wrappers(x.strip()) for x in re.split(r"&&|\|\||[;&|\n]", s) if x.strip()]

    # ---- A/B. rm wipes + find -delete on catastrophic roots ----
    for seg in segs:
        if re.match(r"rm\b", seg):
            if re.search(r"--no-preserve-root\b", seg):
                return "rm --no-preserve-root — defeats the root-deletion failsafe"
            sh = _shorts(seg)
            lo = _longs(seg)
            recursive = ("r" in sh) or ("R" in sh) or ("--recursive" in lo)
            force = ("f" in sh) or ("--force" in lo)
            if recursive and force and _has_target(seg):
                return "rm -rf on a system/home root: `%s`" % seg[:100]
        if re.match(r"find\b", seg) and _has_target(seg) and \
                re.search(r"(-delete\b|-exec(?:dir)?\s+rm\b)", seg):
            return "find on a system/home root with -delete / -exec rm: `%s`" % seg[:100]

    # ---- C. device / disk destruction (anchored to the segment start so a tool name mentioned inside
    #         another command's quoted argument, e.g. `git commit -m "...dd of=/dev/sda..."`, is ignored) ----
    for seg in segs:
        if re.match(r"dd\b", seg) and re.search(r"\bof=" + DEV, seg):
            return "dd writing to a block device: `%s`" % seg[:100]
        if re.match(r"mkfs(?:\.[A-Za-z0-9]+)?\b\s+\S", seg):
            return "mkfs — formatting a filesystem"
        if re.match(r"wipefs\b", seg) and re.search(DEV, seg):
            return "wipefs on a block device"
        if re.match(r"blkdiscard\b", seg) and re.search(DEV, seg):
            return "blkdiscard on a block device"
        if re.match(r"shred\b", seg) and re.search(DEV, seg):
            return "shred on a block device"
        if re.match(r"sgdisk\b", seg) and re.search(r"(--zap(-all)?|(?<!\S)-Z\b)", seg):
            return "sgdisk --zap — destroys partition tables"
        if re.match(r"sfdisk\b", seg) and re.search(DEV, seg):
            return "sfdisk writing a partition table to a device"
        if re.match(r"diskutil\b", seg, re.I) and \
                re.search(r"\b(eraseDisk|eraseVolume|zeroDisk|randomDisk|reformat|secureErase|"
                          r"apfs\s+delete\w*)\b", seg, re.I):
            return "diskutil erase/zero/delete — destroys a disk/volume"

    # ---- D. overwrite a block device / critical file (redirection or tee) ----
    if re.search(r">\s*" + DEV, whole_nq):
        return "redirecting output onto a block device"
    if re.search(r"\btee\b\s+(?:-\S+\s+)*" + DEV, whole_nq):
        return "tee writing to a block device"
    if re.search(r">\s*" + CRIT + r"\b", whole_nq) or \
            re.search(r"\b(?:dd|tee)\b[^|;&]*\b(?:of=)?" + CRIT + r"\b", whole_nq):
        return "overwriting a critical system file"

    # ---- E. fork bombs ----
    if re.search(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", whole_nq):
        return "fork bomb ( :(){ :|:& };: )"
    if re.search(r"\b([A-Za-z_]\w*)\s*\(\)\s*\{[^}]*\b\1\b[^}]*\|[^}]*&[^}]*\}", whole_nq):
        return "fork bomb (self-replicating function piped to itself in the background)"

    # ---- F. recursive chmod/chown on system roots ----
    for seg in segs:
        if re.match(r"ch(?:mod|own|grp)\b", seg):
            if ("R" in _shorts(seg)) or ("--recursive" in _longs(seg)):
                if _has_target(seg):
                    return "recursive chmod/chown on a system/home root: `%s`" % seg[:100]

    # ---- G. opaque download-and-execute ----
    if re.search(r"\b(?:curl|wget|fetch)\b[^|]*\|\s*(?:sudo\s+|doas\s+)?"
                 r"(?:sh|bash|zsh|ksh|dash|fish|python3?|perl|ruby|node)\b", whole_nq):
        return "piping a network download straight into a shell/interpreter (curl|bash)"
    if re.search(r"\bbase64\b[^|]*(?:-d|--decode)\b[^|]*\|\s*(?:sudo\s+)?(?:sh|bash|zsh)\b", whole_nq) or \
            re.search(r"\|\s*base64\s+(?:-d|--decode)\s*\|\s*(?:sudo\s+)?(?:sh|bash|zsh)\b", whole_nq):
        return "decoding base64 straight into a shell (base64 -d | sh)"
    if re.search(r"\beval\b[^\n]*\$\(\s*(?:curl|wget|fetch|base64)\b", whole_dq) or \
            re.search(r"\beval\b\s*\"?\$\(\s*(?:curl|wget|fetch)\b", whole_dq):
        return "eval of a network download / base64 ( eval \"$(curl ...)\" )"

    # ---- H. git clean catastrophes (ignored-file wipe, e.g. .env) ----
    for seg in segs:
        if re.match(r"git\s+clean\b", seg):
            sh = _shorts(seg)
            if "x" in sh and "f" in sh:
                return "git clean -x — irreversibly deletes ignored + untracked files (e.g. .env)"

    return None


def check_powershell(cmd):
    """Minimal PowerShell coverage for catastrophic cmdlets."""
    s = re.sub(r"\s+", " ", cmd).strip()
    if not s:
        return None
    if re.search(r"\bRemove-Item\b", s, re.I) and re.search(r"-Recurse\b", s, re.I) and \
            re.search(r"-Force\b", s, re.I) and \
            re.search(r"(?:^|\s)(?:[A-Za-z]:\\?(?:\s|$|\*)|\$HOME|~|\$env:USERPROFILE|"
                      r"\$env:SystemRoot|C:\\Windows|C:\\Users)", s, re.I):
        return "Remove-Item -Recurse -Force on a drive/system/home root"
    if re.search(r"\b(?:Format-Volume|Clear-Disk|Remove-Partition|Reset-PhysicalDisk|"
                 r"Initialize-Disk)\b", s, re.I):
        return "destructive disk cmdlet (Format-Volume / Clear-Disk / ...)"
    return None


def main():
    try:
        d = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # can't parse → don't interfere
    if not isinstance(d, dict):
        sys.exit(0)
    tn = d.get("tool_name", "") or ""
    if tn not in ("Bash", "PowerShell"):
        sys.exit(0)  # only guards shell tools (the hook matcher already scopes this; belt-and-suspenders)
    ti = d.get("tool_input", {}) or {}
    cmd = (ti.get("command", "") or "") if isinstance(ti, dict) else ""
    if not cmd:
        sys.exit(0)
    try:
        reason = check_powershell(cmd) if tn == "PowerShell" else check_bash(cmd)
    except Exception:
        sys.exit(0)  # fail OPEN on a matcher bug — never brick the shell
    if reason:
        sys.stderr.write(
            "[MAGICIAN HARD-GATE] Refused: catastrophic command — " + reason + ".\n"
            "This is an absolute block against system/user-data destruction. It cannot be overridden "
            "by permissions, allow-rules, or auto mode. Do NOT retry, rephrase, or wrap it. If this is "
            "genuinely intended, the human must run it themselves in a terminal outside the agent.\n")
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
