"""Latency contract for the destructive guard's fast path (scripts/destructive-guard.sh).

The guard runs before every Bash and PowerShell call, and since 5.0 it fails closed (`onFailure:
block` with a 5-second timeout in hooks/hooks.json), so its cost on an ordinary command is paid on
every tool call and a slow guard would block work rather than let it through. The fast path at the
top of the script allows a command that holds no candidate token without running the full checks.

This file proves two things: 200 benign commands have a median wall time under 40 ms, and the
fast path never allows a command the full checks would catch: every candidate-token list the fast
path uses is built from, or covers, the guard's own token lines and per-command rules, checked
here statically, while the parity corpus in test_destructive_guard.py checks the verdicts.

The timing bar is scaled by a baseline (a bash process that does nothing) and the test is skipped
on a runner where that baseline alone is slow, so a loaded CI machine fails nothing for being slow.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "destructive-guard.sh"
BASH = "/bin/bash" if Path("/bin/bash").exists() else (shutil.which("bash") or "bash")

MEDIAN_LIMIT_MS = 40.0
BASELINE_SKIP_MS = 20.0   # a runner where an empty bash process takes longer than this is too slow to measure
BASELINE_FREE_MS = 4.0    # a baseline up to this is normal; above it the limit grows in proportion

# 200 ordinary commands of the kind Claude runs all day. Most hold no candidate token and take the fast
# path; a few (rm, chmod, find, env with an operand, git push, git reset --soft) go through the full
# checks, as in real use.
BENIGN = [
    "git status", "git diff", "git log --oneline -5", "git add -A", "git commit -m \"fix typo\"",
    "git push origin main", "git pull --rebase", "git checkout -b feature/x", "git stash", "git stash pop",
    "npm test", "npm run build", "npm run lint", "npm ci", "npm install", "npm run dev",
    "yarn test", "pnpm build", "pnpm install --frozen-lockfile", "tsc --noEmit",
    "python3 -m pytest", "python3 -m pytest tests/ -q", "python3 -m unittest discover", "pip install -r requirements.txt",
    "ruff check .", "ruff format .", "black .", "mypy src", "pytest -k test_login",
    "go build ./...", "go test ./...", "go vet ./...", "go mod tidy", "gofmt -l .",
    "cargo build", "cargo test", "cargo clippy", "cargo fmt", "cargo run -- --help",
    "make", "make test", "make build", "make lint", "cmake -B build",
    "ls -la", "ls -la src/", "pwd", "whoami", "date", "uptime", "df -h", "du -sh .",
    "grep -rn TODO src/", "grep -c error app.log", "wc -l README.md", "head -20 package.json", "tail -f app.log",
    "sed -n 1,40p main.py", "sort names.txt | uniq -c", "cut -d, -f2 data.csv", "tr a-z A-Z < in.txt",
    "mkdir -p build/out", "touch .keep", "cp a.txt b.txt", "mv old.txt new.txt", "ln -s target link",
    "echo hello", "echo \"build done\"", "printf '%s\\n' one two", "true", "false || echo failed",
    "docker build -t app .", "docker compose up -d", "docker ps", "docker logs app", "docker compose down",
    "kubectl get pods", "kubectl describe pod web", "kubectl logs web", "terraform plan", "terraform fmt",
    "gh pr list", "gh pr view 12", "gh run list", "gh issue list", "glab mr list",
    "node server.js", "node --version", "npm --version", "python3 --version", "go version",
    "which node", "type python3", "command -v jq", "jq . package.json", "jq -r .version package.json",
    "diff a.txt b.txt", "cmp a.bin b.bin", "md5sum file", "sha256sum file", "cksum file",
    "tar czf out.tgz src/", "tar xzf out.tgz", "zip -r out.zip src/", "unzip out.zip", "gzip -k log.txt",
    "ps aux | grep node", "top -l 1", "kill 1234", "jobs",
    "cd src && npm test", "cd .. && ls", "(cd build && make)", "{ npm test; npm run lint; }", "npm test && npm run build",
    "npm test || echo tests failed", "npm run lint 2>&1 | tail -20", "npm test > test.log 2>&1", "echo done >> notes.txt", "sort < in.txt > out.txt",
    "for f in *.py; do echo $f; done", "while read l; do echo $l; done < list.txt", "if [ -f x ]; then echo yes; fi", "case $x in a) echo a;; esac", "[ -d build ] && echo built",
    "VAR=1 npm test", "NODE_ENV=production node app.js", "PYTHONPATH=src pytest", "export NODE_ENV=test", "unset DEBUG",
    "prettier --write src/", "eslint src/ --fix", "stylelint \"**/*.css\"", "tsc -p tsconfig.json", "vite build",
    "bundle install", "bundle exec rspec", "rails db:migrate", "rake test", "gem list",
    "mvn test", "mvn package -DskipTests", "gradle build", "./gradlew test", "java -version",
    "dotnet build", "dotnet test", "dotnet run", "nuget restore", "msbuild app.sln",
    "swift build", "swift test", "xcodebuild -list", "pod install", "flutter test",
    "php artisan test", "composer install", "php -v", "composer dump-autoload", "phpunit",
    "psql -c 'select 1'", "mysql -e 'select 1'", "sqlite3 app.db .tables", "redis-cli ping", "mongosh --eval 'db.stats()'",
    "ctx status", "kg query login handler", "kg blast src/auth.py", "magician-ui status", "jira issue view ABC-1",
    "git rebase -i HEAD~3", "git cherry-pick abc123", "git tag v1.0.0", "git remote -v", "git branch -a",
    "git worktree list", "git bisect start", "git blame main.py", "git show HEAD", "git reset --soft HEAD~1",
    "python3 scripts/report.py --since 2026-01-01", "node scripts/build.js --watch", "bash scripts/gate.sh", "sh ./run.sh", "./configure --prefix=/opt/app",
    "awk '{print $1}' data.txt", "xargs -n1 echo < list.txt", "basename /a/b/c.txt", "dirname /a/b/c.txt", "realpath .",
    "env FOO=1 ./run.sh", "printenv HOME", "set -o pipefail", "declare -p HOME", "export PATH=$PATH:/opt/bin",
    "find . -name '*.py' -newer main.py", "find src -type f | wc -l", "rm -f build/*.o", "rm -rf node_modules", "chmod +x run.sh",
]
assert len(BENIGN) == 200, len(BENIGN)


def _event(command: str) -> str:
    return json.dumps({"session_id": "t", "hook_event_name": "PreToolUse", "tool_name": "Bash",
                       "tool_input": {"command": command}})


class _Runner:
    def __init__(self, tmp: str) -> None:
        self.env = {
            "PATH": "/usr/bin:/bin", "HOME": tmp, "LC_ALL": "C",
            "CLAUDE_PLUGIN_ROOT": str(ROOT), "CLAUDE_PLUGIN_DATA": os.path.join(tmp, "data"),
            "MAGICIAN_HOME": os.path.join(tmp, "magician"), "MAGICIAN_SETTINGS": os.path.join(tmp, "settings.json"),
            "CLAUDE_ENV_FILE": os.path.join(tmp, "session.env"),
        }
        self.tmp = tmp

    def timed(self, argv: list, stdin: str) -> tuple:
        start = time.perf_counter()
        proc = subprocess.run(argv, input=stdin, text=True, capture_output=True, env=self.env, cwd=self.tmp,
                              timeout=30, check=False)
        return (time.perf_counter() - start) * 1000.0, proc


class GuardLatencyTests(unittest.TestCase):
    def test_median_over_200_benign_commands_is_under_40ms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            r = _Runner(tmp)
            base_script = Path(tmp) / "nothing.sh"
            base_script.write_text("exit 0\n", encoding="utf-8")
            baseline = statistics.median(r.timed([BASH, str(base_script)], "")[0] for _ in range(20))
            if baseline > BASELINE_SKIP_MS:
                self.skipTest(f"slow runner: an empty bash process takes {baseline:.1f} ms (limit {BASELINE_SKIP_MS} ms)")
            limit = MEDIAN_LIMIT_MS * max(1.0, baseline / BASELINE_FREE_MS)
            times = []
            for command in BENIGN:
                ms, proc = r.timed([BASH, str(GUARD)], _event(command))
                self.assertEqual(proc.returncode, 0, f"{command!r}: {proc.stderr}")
                self.assertEqual(proc.stdout, "", f"{command!r} got a verdict: {proc.stdout}")
                times.append(ms)
            median = statistics.median(times)
            self.assertLess(median, limit,
                            f"median {median:.1f} ms over {len(times)} benign commands (limit {limit:.1f} ms, "
                            f"baseline {baseline:.1f} ms)")


class FastPathCoverageTests(unittest.TestCase):
    """The fast path may only allow what no full check could catch."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = GUARD.read_text(encoding="utf-8")

    def _list(self, name: str, quote: str = '"') -> list:
        m = re.search(rf"^{name}={quote}([^{quote}]*){quote}$", self.text, re.M)
        self.assertIsNotNone(m, f"no {name}= token line")
        return m.group(1).split()

    def test_fast_path_runs_before_every_check_and_uses_the_shared_lists(self) -> None:
        pos = self.text.index('fast_path "$CMD" && exit 0')
        for marker in ("check_pipeline_text \"$whole_nq\"", "for seg in \"${FSEGS[@]}\"", "check_forkbomb",
                       "soft_block \"pipe-to-shell", "# ---- normalize case once"):
            self.assertGreater(self.text.index(marker), pos, marker)
        body = self.text[self.text.index("fast_path() {"):self.text.index('fast_path "$CMD" && exit 0')]
        self.assertIn("$DOWNLOADERS", body, "the downloader words come from the shared DOWNLOADERS line")
        self.assertIn("$EVALWORD", body)
        self.assertIn("$FAST_HEADS", body)
        self.assertIn("$FAST_PARTS", body)
        for helper in ("lower ", "drop_char \"$t\" -", "drop_char \"$t\" '\"'", "drop_char \"$t\" \"'\""):
            self.assertIn(helper, body, f"the fast path normalizes the text like the rules do ({helper.strip()})")

    def test_every_per_command_rule_head_is_a_fast_path_head(self) -> None:
        """Every command word a `case "$RH_HEAD"` / `case "$_fw"` arm names in the per-command rules."""
        heads = set(self._list("FAST_HEADS"))
        code = "\n".join(l for l in self.text.splitlines() if not l.lstrip().startswith("#"))
        arms = set()
        lines = code.splitlines()
        for i, line in enumerate(lines):
            m = re.match(r'^(\s*)case "\$(?:RH_HEAD|_fw)" in$', line)
            if not m:
                continue
            indent = m.group(1)
            for nxt in lines[i + 1:]:   # the arms sit one level in; the matching esac at the case's level
                if nxt == indent + "esac":
                    break
                a = re.match(r"^" + indent + r"  ([A-Za-z0-9_.|*]+)\)", nxt)
                if a:
                    for word in a.group(1).split("|"):
                        arms.add(word.rstrip(".*"))
        self.assertTrue({"rm", "dd", "mkfs", "git", "env", "set"} <= arms, sorted(arms))
        # git is caught through its subcommands: clean (hard), push and reset (soft), each a head.
        self.assertIn('_gsub="${1:-}"', code)
        for sub in ("clean", "push", "reset"):
            self.assertIn(sub, heads)
            self.assertIn('[ "$_gsub" = %s ]' % sub, code)
        # cd is context for the rm and find rules (CD_HINT), not a rule: a cd with neither is harmless.
        self.assertIn('if [ "$RH_HEAD" = cd ] || [ "$RH_HEAD" = pushd ]; then', code)
        self.assertNotIn("cd", heads)
        missing = sorted(w for w in arms - {"git"} if w not in heads)
        self.assertEqual(missing, [], f"per-command rule heads missing from FAST_HEADS: {missing}")

    def test_network_and_decoder_words_are_fast_path_heads(self) -> None:
        heads = set(self._list("FAST_HEADS"))
        for word in ("curl", "wget", "nc", "ncat", "ssh", "scp", "rsync"):   # the trifecta's _net words
            self.assertTrue(word in heads or word in self._list("DOWNLOADERS"), word)
        self.assertIn("base64", heads)
        self.assertIn("cat", heads)   # the soft credential-read rules

    def test_substring_rules_are_fast_path_parts(self) -> None:
        parts = set(self._list("FAST_PARTS", "'"))
        for frag in ("removeitem", "formatvolume", "cleardisk", "removepartition", "resetphysicaldisk",
                     "initializedisk", "claude_", "/proc/", "/sessionenv/", "/etc/", "${!"):
            self.assertIn(frag, parts, frag)
        # every device prefix is_device() names, hyphen-free and lowercase
        m = re.search(r"is_device\(\) \{.*?\n\}", self.text, re.S)
        self.assertIsNotNone(m)
        for dev in re.findall(r'"(/dev/[a-z]+/?)"', m.group(0)):
            self.assertIn(dev, parts, dev)

    def test_fork_bomb_shapes_need_a_brace_and_an_ampersand(self) -> None:
        """check_forkbomb returns early without { | and &; the fast path keeps { with & as a candidate."""
        fb = self.text[self.text.index("check_forkbomb() {"):self.text.index("# The whole command, and each shell -c payload")]
        self.assertIn("case \"$text\" in *'{'*) ;; *) return 0 ;; esac", fb)
        self.assertIn("case \"$text\" in *'&'*) ;; *) return 0 ;; esac", fb)
        body = self.text[self.text.index("fast_path() {"):self.text.index('fast_path "$CMD" && exit 0')]
        self.assertIn("*'{'*) case \"$t\" in *'&'*) return 1 ;; esac ;;", body)


if __name__ == "__main__":
    unittest.main()
