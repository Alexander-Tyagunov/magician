"""Lore corpus contract: `lore/<stack>.md` cores + one `lore/deep/<stack>.md` per stack.

Cores are injected at SessionStart under a fixed budget; deep-dive files are read on demand, one
`## ` section at a time (Grep `^## ` -> Read offset/limit). A dangling `lore/deep/<t>.md#<id>`
pointer or a section without its anchor silently drops guidance, and a stray `lore/<t>/` tree
breaks the plugin-size budget, so all of it is gated here.
"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[2]
LORE = ROOT / "lore"
DEEP = LORE / "deep"
SCAN = ["lore", "skills", "agents", "scripts", "tools", "hooks", "evals", "monitors", "README.md"]
# A lore path starts a token, optionally after the plugin-root variable or ./ and ../ segments.
BOUND = r"(?<![\w./-])(?:\$\{CLAUDE_PLUGIN_ROOT\}/|\$CLAUDE_PLUGIN_ROOT/|(?:\.\.?/)+)?"
REF_DEEP = re.compile(BOUND + r"lore/deep/([a-z0-9-]+)\.md(?:#(\{[a-z0-9,-]+\}|[a-z0-9-]+))?")
REF_CORE = re.compile(BOUND + r"lore/([a-z0-9-]+)\.md")
OLD_TREE = re.compile(BOUND + r"lore/(?!deep/)[a-z0-9-]+/")
SECTION = re.compile(r'^## (.+) <a id="([a-z0-9]+(?:-[a-z0-9]+)*)"></a>$')
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
PLUGIN_ROOT_VAR = re.compile(r"^\$(?:\{CLAUDE_PLUGIN_ROOT\}|CLAUDE_PLUGIN_ROOT)(?=/)")
ROOTED_LORE = re.compile(r"\$(?:\{CLAUDE_PLUGIN_ROOT\}|CLAUDE_PLUGIN_ROOT)/(lore(?:/[^\s\"'`()\[\]<>|;]*)?)")
MD_LINK = re.compile(r"!?\[(?:[^\]\\]|\\.)*\]\(\s*(<[^>\n]*>|[^)\s]+)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
MD_REF_DEF = re.compile(r"^ {0,3}\[[^\]]+\]:\s*(<[^>\n]*>|\S+)")
SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
MAX_FILE = 256 * 1024
MAX_FILES = 512


def fenced_lines(text: str):
    """(line number, line, inside a code fence) for every line; the fence lines themselves count as inside."""
    fence = None
    for n, line in enumerate(text.split("\n"), 1):
        m = FENCE.match(line)
        if fence is None and m:
            fence = m.group(1)
            yield n, line, True
            continue
        if fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and line.strip() == m.group(1):
                fence = None
            yield n, line, True
            continue
        yield n, line, False


def outside_fences(text: str):
    return ((n, line) for n, line, fenced in fenced_lines(text) if not fenced)


def md_anchors(md: str) -> set[str]:
    """GitHub heading slugs (a repeated slug gets -1, -2, ...) plus explicit <a id> / <a name> anchors."""
    seen: dict[str, int] = {}
    for _, line in outside_fences(md):
        m = re.match(r"^ {0,3}#{1,6}[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$", line)
        if not m:
            continue
        title = re.sub(r"<[^>]+>", "", re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", m.group(1)))
        slug = re.sub(r"[^\w\- ]", "", title.strip().lower()).replace(" ", "-")
        seen[slug] = seen.get(slug, -1) + 1
        if seen[slug]:
            seen[f"{slug}-{seen[slug]}"] = 0
    return set(seen) | set(re.findall(r'<a\s+(?:id|name)="([^"]+)"', md))


@lru_cache(maxsize=None)
def file_anchors(path: Path) -> frozenset[str]:
    return frozenset(md_anchors(path.read_text(encoding="utf-8")))


def md_links(text: str):
    """(line number, target) for inline links, images and reference definitions outside code."""
    for n, line in outside_fences(text):
        line = re.sub(r"``.+?``|`[^`]*`", "", line)
        for m in [*MD_LINK.finditer(line), *MD_REF_DEF.finditer(line)]:
            target = m.group(1)
            yield n, target[1:-1] if target.startswith("<") else target


def link_problem(src: Path, target: str, root: Path = ROOT) -> str | None:
    """Why a link target written in src does not resolve, or None. A ${CLAUDE_PLUGIN_ROOT} or leading /
    target is taken from the repo root, anything else from src's directory; #frag alone is src itself."""
    if SCHEME.match(target):
        return None  # http(s), mailto and other URLs
    rel, _, frag = target.partition("#")
    rel = unquote(rel)
    if m := PLUGIN_ROOT_VAR.match(rel):
        dest = root / rel[m.end():].lstrip("/")
    elif rel.startswith("/"):
        dest = root / rel.lstrip("/")
    else:
        dest = src.parent / rel if rel else src
    dest = dest.resolve()
    if not dest.is_relative_to(root.resolve()):
        return f"link escapes the repo: {target!r}"
    if not dest.exists():
        return f"dangling link {target!r}"
    if frag and dest.suffix == ".md" and dest.is_file() and unquote(frag) not in file_anchors(dest):
        return f"no anchor #{frag} in {dest.relative_to(root.resolve())}"
    return None


def deep_files() -> list[Path]:
    return sorted(DEEP.glob("*.md"))


def section_ids(path: Path) -> list[str]:
    return [m.group(2) for _, l in outside_fences(path.read_text(encoding="utf-8"))
            if (m := SECTION.match(l))]


def tracked_markdown() -> list[Path]:
    """Tracked .md files outside tests/ that are present on disk (every .md when git lists none, as in
    a copy without .git). Dot-directories are skipped only below ROOT, so an install path such as
    ~/.claude/plugins/... still walks."""
    files: list[Path] = []
    try:
        out = subprocess.run(["git", "ls-files", "-z", "--", "*.md"], cwd=ROOT, capture_output=True,
                             check=True).stdout
        files = [ROOT / n for n in out.decode().split("\0") if n]
    except (OSError, subprocess.CalledProcessError):
        pass
    if not files:
        files = [p for p in ROOT.rglob("*.md")
                 if not any(part.startswith(".") for part in p.relative_to(ROOT).parts)]
    return sorted(p for p in files if p.is_file() and p.relative_to(ROOT).parts[0] != "tests")


def scanned_files() -> list[Path]:
    out = []
    for entry in SCAN:
        p = ROOT / entry
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            out += [f for f in p.rglob("*") if f.is_file() and "__pycache__" not in f.parts
                    and not f.name.startswith(".")
                    and f.suffix in {".md", ".sh", ".json", ".py", ""}]
    return sorted(out)


class LoreLayoutTests(unittest.TestCase):
    def test_lore_has_only_cores_and_the_deep_dir(self) -> None:
        self.assertTrue(DEEP.is_dir(), "lore/deep/ missing")
        for p in sorted(LORE.iterdir()):
            if p.name.startswith("."):
                continue  # .DS_Store etc. are never tracked
            with self.subTest(path=p.name):
                if p.is_dir():
                    if p.name == "deep":
                        continue
                    self.assertFalse(any(p.rglob("*")), f"lore/{p.name}/ must be merged into lore/deep/{p.name}.md")
                else:
                    self.assertEqual(p.suffix, ".md")
        for p in DEEP.iterdir():
            if p.name.startswith("."):
                continue
            self.assertTrue(p.is_file() and p.suffix == ".md", f"unexpected lore/deep/{p.name}")

    def test_every_deep_file_has_a_core(self) -> None:
        self.assertGreaterEqual(len(deep_files()), 100)
        for p in deep_files():
            with self.subTest(deep=p.name):
                self.assertTrue((LORE / p.name).is_file(), f"lore/deep/{p.name} has no core lore/{p.name}")

    def test_deep_file_structure(self) -> None:
        for p in deep_files():
            text = p.read_text(encoding="utf-8")
            lines = list(outside_fences(text))
            h1 = [l for _, l in lines if re.match(r"^# ", l)]
            h2 = [l for _, l in lines if l.startswith("## ")]
            ids = section_ids(p)
            with self.subTest(deep=p.name):
                self.assertEqual(len(h1), 1, "exactly one H1")
                self.assertTrue(h1[0].endswith(" — deep dive"), h1[0])
                self.assertTrue(text.startswith(h1[0] + "\n"), "H1 must be the first line")
                self.assertEqual(len(h2), len(ids), "every ## heading must end with its <a id> anchor")
                self.assertGreaterEqual(len(ids), 1)
                self.assertEqual(len(ids), len(set(ids)), "duplicate section id")
                head = text.split("\n## ", 1)[0]
                self.assertIn("Grep `^## `", head, "access note (Grep then Read offset/limit) missing")
                toc = re.findall(r"\]\(#([a-z0-9-]+)\)", next(l for l in head.split("\n") if l.startswith("Sections: ")))
                self.assertEqual(toc, ids, "Sections: line must list every section id in file order")
                self.assertFalse(any(re.match(r"^#{6}", l) for _, l in lines), "headings deeper than H5")

    def test_core_pointer_lists_exactly_the_sections(self) -> None:
        for p in deep_files():
            core = (LORE / p.name).read_text(encoding="utf-8")
            listed = []
            for m in REF_DEEP.finditer(core):
                if m.group(1) == p.stem and m.group(2):
                    listed += m.group(2).strip("{}").split(",")
            with self.subTest(core=p.name):
                self.assertEqual(sorted(set(listed)), sorted(section_ids(p)),
                                 f"lore/{p.name} pointer must list every section of lore/deep/{p.name}")

    def test_under_directory_validator_file_size(self) -> None:
        for p in [*LORE.glob("*.md"), *deep_files()]:
            with self.subTest(path=str(p.relative_to(ROOT))):
                self.assertLess(p.stat().st_size, MAX_FILE)

    def test_bundled_source_attribution_is_kept(self) -> None:
        self.assertIn("rmcp-server-kit", (LORE / "rust.md").read_text(encoding="utf-8").split("\n", 1)[0])
        head = (DEEP / "rust.md").read_text(encoding="utf-8").split("\n## ", 1)[0]
        for needle in ("rmcp-server-kit", "MIT OR Apache-2.0", "RUST_GUIDELINES.md"):
            self.assertIn(needle, head, "the hoisted attribution must precede the first section")


class LoreReferenceTests(unittest.TestCase):
    def test_every_lore_reference_resolves(self) -> None:
        ids = {p.stem: set(section_ids(p)) for p in deep_files()}
        for f in scanned_files():
            try:
                text = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for n, line in outside_fences(text):
                for m in REF_DEEP.finditer(line):
                    t, frag = m.group(1), m.group(2)
                    with self.subTest(file=str(f.relative_to(ROOT)), line=n, ref=m.group(0)):
                        self.assertIn(t, ids, f"no lore/deep/{t}.md")
                        for s in (frag.strip("{}").split(",") if frag else []):
                            self.assertIn(s, ids[t], f"no section #{s} in lore/deep/{t}.md")
                for m in REF_CORE.finditer(line):
                    with self.subTest(file=str(f.relative_to(ROOT)), line=n, ref=m.group(0)):
                        self.assertTrue((LORE / f"{m.group(1)}.md").is_file(), f"no lore/{m.group(1)}.md")

    def test_reference_patterns_cover_rooted_and_relative_forms(self) -> None:
        for text, core in (("`${CLAUDE_PLUGIN_ROOT}/lore/deep/rust.md#{a,b}`", "rust"),
                           ('cat "$CLAUDE_PLUGIN_ROOT/lore/deep/go.md"', "go"),
                           ("[l](./lore/deep/sql.md#joins)", "sql"),
                           ("[x](../../lore/deep/java.md)", "java")):
            with self.subTest(text=text):
                self.assertEqual([m.group(1) for m in REF_DEEP.finditer(text)], [core])
        for text, core in (("[x](../lore/python.md)", "python"), ("see lore/go.md.", "go"),
                           ("${CLAUDE_PLUGIN_ROOT}/lore/react.md", "react")):
            with self.subTest(text=text):
                self.assertEqual([m.group(1) for m in REF_CORE.finditer(text)], [core])
        for text in ("src/lore/go.md", "folklore/go.md", "a.b/lore/go.md", "$OTHER_ROOT/lore/go.md"):
            with self.subTest(text=text):
                self.assertEqual(REF_CORE.findall(text), [])
        self.assertEqual(OLD_TREE.findall("[x](../lore/rust/intro.md)"), ["../lore/rust/"])

    def test_link_resolver_flags_missing_files_and_anchors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "lore" / "deep").mkdir(parents=True)
            (root / "skills" / "demo").mkdir(parents=True)
            (root / "lore" / "go.md").write_text("# Go core\n## Errors, wrapped\n## Errors, wrapped\n", encoding="utf-8")
            (root / "lore" / "deep" / "go.md").write_text('# Go\n## Context <a id="ctx"></a>\n', encoding="utf-8")
            skill = root / "skills" / "demo" / "SKILL.md"
            skill.write_text("# Demo skill\n## Steps\n", encoding="utf-8")
            file_anchors.cache_clear()
            ok = ["../../lore/go.md", "../../lore/go.md#errors-wrapped", "../../lore/go.md#errors-wrapped-1",
                  "./../../lore/deep/go.md#ctx", "${CLAUDE_PLUGIN_ROOT}/lore/deep/go.md#ctx", "/lore/go.md",
                  "$CLAUDE_PLUGIN_ROOT/lore/", "#steps", "#demo-skill", "https://example.test/x#y",
                  "mailto:a@example.test", "../../lore/deep/go%2Emd"]
            bad = ["../lore/go.md", "../../lore/nope.md", "../../lore/go.md#errors-wrapped-2",
                   "${CLAUDE_PLUGIN_ROOT}/lore/deep/go.md#intro", "#nope", "../../../outside.md"]
            for target in ok:
                with self.subTest(ok=target):
                    self.assertIsNone(link_problem(skill, target, root))
            for target in bad:
                with self.subTest(bad=target):
                    self.assertIsNotNone(link_problem(skill, target, root))
            file_anchors.cache_clear()
        md = "[a](x.md) ![i](<img one.png> \"t\") `[c](code.md)` [`b`](y.md#z)\n```\n[f](fenced.md)\n```\n[r]: ref.md\n"
        self.assertEqual(list(md_links(md)), [(1, "x.md"), (1, "img one.png"), (1, "y.md#z"), (5, "ref.md")])

    def test_markdown_links_and_anchors_resolve_in_every_tracked_file(self) -> None:
        files = tracked_markdown()
        self.assertGreater(len(files), 100)
        for f in files:
            text = f.read_text(encoding="utf-8")
            for n, target in md_links(text):
                problem = link_problem(f, target)
                with self.subTest(file=f"{f.relative_to(ROOT)}:{n}", target=target):
                    self.assertIsNone(problem, problem)

    def test_plugin_root_lore_pointers_resolve(self) -> None:
        """${CLAUDE_PLUGIN_ROOT}/lore/... outside link syntax, fenced lines included (they are run as-is)."""
        ids = {p.stem: set(section_ids(p)) for p in deep_files()}
        for f in sorted({*scanned_files(), *tracked_markdown()}):
            try:
                text = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for n, line, _ in fenced_lines(text):
                for m in ROOTED_LORE.finditer(line):
                    path, _, frag = m.group(1).rstrip(".,:").partition("#")
                    if re.search(r"[{}$*]", path):
                        continue  # a placeholder such as ${TECH}
                    with self.subTest(file=f"{f.relative_to(ROOT)}:{n}", ref=m.group(0)):
                        dest = ROOT / path
                        self.assertTrue(dest.exists(), f"no {path}")
                        for s in (frag.strip("{}").split(",") if frag else []):
                            known = ids.get(dest.stem, set()) if dest.parent == DEEP else file_anchors(dest)
                            self.assertIn(s, known, f"no section #{s} in {path}")

    def test_no_old_style_deep_tree_paths(self) -> None:
        for f in scanned_files():
            if f.name == "test_lore.py":
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for n, line in enumerate(text.split("\n"), 1):
                for m in OLD_TREE.finditer(line):
                    with self.subTest(file=str(f.relative_to(ROOT)), line=n):
                        self.fail(f"old lore/<topic>/ path {m.group(0)!r} — use lore/deep/<topic>.md#<id>")


class LoreBudgetTests(unittest.TestCase):
    """SessionStart run for real on fixture projects, with install-length plugin root and data paths:
    each stack's listed cores are injected and the context stays under the 9,500-character cap.

    The listed cores are the language, framework and engine plus the databases foundation. logging and
    other libraries fill what is left. A Next.js project also detects javascript (package.json) and
    react; not all of them fit next to typescript + nextjs + react + postgres, and the hook drops the
    generic ones (javascript, databases, logging) first."""

    CAP = 9500   # Claude Code truncates hook context past 10,000 characters
    PATH_LEN = 90
    # (fixture files, the hook's "Detected stack:" value, cores that must be injected besides security)
    STACKS = [
        ({"pom.xml": "<artifactId>spring-boot-starter-web</artifactId><groupId>org.postgresql</groupId>"},
         "java,spring,jdbc,databases,postgres", ["java", "spring", "databases", "postgres"]),
        ({"requirements.txt": "Django==4.2\npsycopg2-binary\n", "tests/.keep": ""},
         "python,django,tdd,databases,postgres", ["python", "django", "databases", "postgres"]),
        ({"package.json": '{"dependencies": {"next": "15", "react": "19", "pg": "8"}}', "tsconfig.json": "{}"},
         "javascript,typescript,nextjs,react,databases,postgres", ["typescript", "nextjs", "react", "postgres"]),
        ({"go.mod": "module example.test/app\nrequire (\n\tgithub.com/gin-gonic/gin v1.10.0\n"
                    "\tgithub.com/jackc/pgx/v5 v5.7.0\n)\n"},
         "go,gin,sqlx,databases,postgres", ["go", "gin", "databases", "postgres"]),
        ({"package.json": '{"dependencies": {"express": "5", "mongoose": "8"}}'},
         "javascript,express,mongoose,databases,mongodb", ["javascript", "express", "databases", "mongodb"]),
    ]

    @staticmethod
    def _long(base: Path, name: str, n: int) -> Path:
        """base/<name><padding>, n characters long in total (longer only when base itself is)."""
        return base / (name + "x" * max(0, n - len(str(base)) - 1 - len(name)))

    def test_realistic_stacks_inject_their_cores_with_a_long_plugin_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = self._long(base, "plugin-root-", self.PATH_LEN)
            root.symlink_to(ROOT)
            data = self._long(base, "plugin-data-", self.PATH_LEN)
            for d in (base / "home", base / "maghome", data):
                d.mkdir()
            env = {"PATH": "/usr/bin:/bin", "LANG": "C", "HOME": str(base / "home"),
                   "CLAUDE_PLUGIN_ROOT": str(root), "CLAUDE_PLUGIN_DATA": str(data),
                   "MAGICIAN_HOME": str(base / "maghome"), "MAGICIAN_DATA": str(base / "magdata"),
                   "MAGICIAN_SETTINGS": str(base / "home" / ".claude" / "settings.json"),
                   "CLAUDE_ENV_FILE": str(base / "session.env")}
            for i, (files, detected, cores) in enumerate(self.STACKS):
                proj = base / f"app{i}"
                for rel, text in files.items():
                    (proj / rel).parent.mkdir(parents=True, exist_ok=True)
                    (proj / rel).write_text(text, encoding="utf-8")
                proc = subprocess.run(["/bin/bash", str(ROOT / "scripts" / "session-start.sh")],
                                      input='{"source": "startup"}', capture_output=True, text=True,
                                      cwd=proj, env=env, timeout=60, check=False)
                with self.subTest(stack=detected):
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    ctx = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
                    injected = re.findall(r"(?m)^\[([a-z0-9-]+)\] ", ctx)
                    self.assertIn(f"Detected stack: {detected}.", ctx)
                    for core in ["security", *cores]:
                        self.assertIn(core, injected, f"{core} starved; injected {injected}")
                    self.assertLessEqual(len(ctx.encode("utf-8")), self.CAP)
                    # The hook cuts anything over the cap from the end, so the voice note comes last.
                    self.assertIn("(voice: scribe)", ctx, "the lore budget overran and the tail was cut")


class PackageLimitTests(unittest.TestCase):
    def test_tracked_file_count_under_validator_limit(self) -> None:
        try:
            out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        files = [f for f in out.decode().split("\0") if f]
        self.assertLessEqual(len(files), MAX_FILES, f"{len(files)} tracked files > {MAX_FILES}")


if __name__ == "__main__":
    unittest.main()
