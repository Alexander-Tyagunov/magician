"""README and policy-document contract for the Claude plugin directory.

The directory renders the README with Markdown image syntax only and rejects remote images, raw HTML
and scripted SVGs. It also expects a privacy policy, a way to report security problems, working
example prompts and an honest list of what the plugin runs. This gate keeps those properties from
regressing: it checks the README's structure, the bundled images, and that every skill, hook script
and plugin option is documented.

Reads files only; runs nothing.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
PRIVACY = ROOT / "PRIVACY.md"
SECURITY = ROOT / "SECURITY.md"
PLUGIN_DIR = ROOT / ".claude-plugin"
PLUGIN_JSON = PLUGIN_DIR / "plugin.json"
HOOKS_JSON = ROOT / "hooks" / "hooks.json"
REPO_URL = "https://github.com/Alexander-Tyagunov/magician"

# Documents in which an image or font path must never appear inside code (fences or inline spans).
DOCS = ("README.md", "CHANGELOG.md", "PRIVACY.md", "SECURITY.md")

# The README opens with the banner as a plain Markdown image. The image's own path is read from that
# line at run time, so no image file name is written into this file.
BANNER_ALT = "magician: plan, build, verify, and ship software with Claude Code"
BANNER_LINE = re.compile(rf"^!\[{re.escape(BANNER_ALT)}\]\(([\w./-]+)\)$")

FENCE_BLOCK = re.compile(r"^```.*?^```", re.S | re.M)
INLINE_CODE = re.compile(r"`[^`\n]+`")
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
LINK_TEXT = re.compile(r"(?<!!)\[([^\]]+)\]\([^)\s]+\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
# Arrows, math/technical symbols, dingbats, emoji and the emoji variation selector.
HEADING_SYMBOL = re.compile("[←-⯿\U0001F000-\U0001FAFF️]")
HTML_TAG = re.compile(r"<(?:[A-Za-z][A-Za-z0-9-]*[\s/>]|/[A-Za-z]|!--)")
RAW_HTML_MARKERS = ("<img", "<picture", "<source", "<svg", "<table", "<div", "<br", "style=", "class=")
IMAGE_OR_FONT_SUFFIX = r"\.(?:svg|png|jpe?g|gif|webp|avif|bmp|ico|woff2?|ttf|otf|eot)\b"
WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")
TABLE_DIVIDER = re.compile(r"^\|(?:\s*:?-{3,}:?\s*\|)+\s*$")
VAGUE_LINK_TEXT = {"here", "click here", "this", "this link", "link", "read more", "more"}

# Anything that makes an SVG dynamic or pulls in external content.
SVG_BAD = [r"<script", r"<animate", r"<set\b", r"<foreignObject", r"<style", r"@import", r"<image\b",
           r"<filter", r"\son[a-z]+\s*=", r'href\s*=\s*"(?!#)', r"url\(\s*[\"']?(?!#)", r"data:"]


def split_markdown(md: str) -> tuple[list[str], list[str], str]:
    """Return (fenced blocks, inline code spans, prose with all code removed)."""
    fences = FENCE_BLOCK.findall(md)
    prose = FENCE_BLOCK.sub("", md)
    inline = INLINE_CODE.findall(prose)
    text = INLINE_CODE.sub("", prose)
    return fences, inline, text


def section(md: str, heading: str) -> str:
    """Body of the `## <heading>` section, up to the next `## ` heading (fences kept intact)."""
    m = re.search(rf"(?m)^## {re.escape(heading)}\s*$", md)
    if not m:
        return ""
    rest = md[m.end():]
    # Blank out fenced blocks (same length) so a "## " line inside a fence can't end the section.
    masked = FENCE_BLOCK.sub(lambda block: " " * len(block.group(0)), rest)
    nxt = re.search(r"(?m)^## ", masked)
    return rest[: nxt.start()] if nxt else rest


def banner_path() -> str:
    """Relative path of the banner image, taken from the README's first line ("" if it doesn't match)."""
    first = README.read_text(encoding="utf-8").splitlines()[0]
    m = BANNER_LINE.match(first)
    return m.group(1) if m else ""


def assets_dir() -> Path | None:
    """Folder that holds the README's bundled images: the banner's folder."""
    rel = banner_path()
    return (ROOT / rel).parent if rel and "/" in rel else None


def is_svg(path: Path) -> bool:
    return path.is_file() and "<svg" in path.read_text(encoding="utf-8", errors="ignore")[:500]


def plugin_icons() -> list[Path]:
    """SVG files in the plugin metadata folder (the icon shown in the plugin directory)."""
    return sorted(p for p in PLUGIN_DIR.iterdir() if is_svg(p))


def svg_files() -> list[Path]:
    folder = assets_dir()
    bundled = sorted(p for p in folder.iterdir() if is_svg(p)) if folder else []
    return bundled + plugin_icons()


def image_or_font_pattern() -> re.Pattern[str]:
    """Image or font file suffixes, plus the images folder and the icon file names found on disk."""
    names = []
    folder = assets_dir()
    if folder:
        names.append(re.escape(folder.relative_to(ROOT).as_posix() + "/"))
    names.extend(re.escape(p.name) for p in plugin_icons())
    return re.compile("(?i)(?:" + "|".join(names + [IMAGE_OR_FONT_SUFFIX]) + ")")


class ReadmeStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.md = README.read_text(encoding="utf-8")
        cls.fences, cls.inline, cls.text = split_markdown(cls.md)

    def test_first_line_is_the_banner_image(self) -> None:
        first = self.md.splitlines()[0]
        m = BANNER_LINE.match(first)
        self.assertIsNotNone(m, "README must open with the banner as a plain Markdown image (no link wrapper)")
        rel = m.group(1)
        self.assertIn("/", rel, "the banner should live in a folder of bundled images")
        self.assertTrue(is_svg(ROOT / rel), f"banner is not a bundled SVG file: {rel}")

    def test_no_html_badges_mermaid_or_alerts(self) -> None:
        lowered = self.text.lower()
        for marker in RAW_HTML_MARKERS:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, lowered, f"raw HTML {marker!r} in README")
        tag = HTML_TAG.search(self.text)
        self.assertIsNone(tag, f"HTML in README: {tag.group(0) if tag else ''}")
        self.assertNotRegex(self.md, r"(?i)shields\.io", "badge in README")
        self.assertNotIn("```mermaid", self.md, "mermaid block in README")
        quoted = [ln for ln in self.text.splitlines() if ln.lstrip().startswith(">")]
        self.assertEqual(quoted, [], f"blockquote or alert in README: {quoted[:3]}")

    def test_images_are_local_files_with_alt_text(self) -> None:
        images = IMAGE.findall(self.text)
        self.assertEqual(len(images), 1, f"README should reference exactly one bundled image: {images}")
        for alt, src in images:
            path = src.split("#")[0]
            with self.subTest(src=src):
                self.assertTrue(alt.strip(), f"empty alt text: {src}")
                self.assertNotRegex(path, r"(?i)^(?:https?:)?//", f"remote image: {src}")
                self.assertTrue((ROOT / path).is_file(), f"missing image: {path}")

    def test_every_asset_is_referenced(self) -> None:
        referenced = {src.split("#")[0] for _, src in IMAGE.findall(self.text)}
        folder = assets_dir()
        self.assertIsNotNone(folder, "banner folder not found from the README's first line")
        for asset in sorted(p for p in folder.iterdir() if p.is_file()):
            rel = asset.relative_to(ROOT).as_posix()
            with self.subTest(asset=rel):
                self.assertIn(rel, referenced, f"unreferenced asset: {rel}")

    def test_headings_are_plain_level_two_or_three(self) -> None:
        for line in self.text.splitlines():
            m = HEADING.match(line)
            if not m:
                continue
            level, title = len(m.group(1)), m.group(2)
            with self.subTest(heading=line):
                self.assertIn(level, (2, 3), "use only ## and ### headings")
                self.assertIsNone(HEADING_SYMBOL.search(title), "symbol or emoji in heading")
                self.assertNotRegex(title, r"(?i)new in \d", "version chip in heading")

    def test_tables_stay_narrow(self) -> None:
        """At most three columns; the hooks table may use four."""
        current_heading = ""
        for line in self.text.splitlines():
            m = HEADING.match(line)
            if m:
                current_heading = m.group(2).strip()
                continue
            if TABLE_DIVIDER.match(line.strip()):
                columns = line.strip().strip("|").count("|") + 1
                limit = 4 if current_heading == "Hooks" else 3
                with self.subTest(section=current_heading):
                    self.assertLessEqual(columns, limit, f"table under '{current_heading}' has {columns} columns")

    def test_link_text_is_descriptive(self) -> None:
        for label in LINK_TEXT.findall(self.text):
            with self.subTest(link=label):
                self.assertNotIn(label.strip().lower(), VAGUE_LINK_TEXT, f"vague link text: {label!r}")

    def test_has_real_prose(self) -> None:
        self.assertGreaterEqual(len(WORD.findall(FENCE_BLOCK.sub("", self.md))), 40)

    def test_examples_section_has_at_least_three_prompts(self) -> None:
        body = section(self.md, "Examples")
        self.assertTrue(body, "no '## Examples' section")
        prompts = [b for b in FENCE_BLOCK.findall(body)
                   if any(ln.strip().startswith("/") for ln in b.splitlines()[1:-1])]
        self.assertGreaterEqual(len(prompts), 3, "Examples needs at least three prompts in text fences")

    def test_every_skill_is_listed(self) -> None:
        for skill in sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")):
            with self.subTest(skill=skill):
                self.assertRegex(self.md, rf"`/{re.escape(skill)}`", f"/{skill} missing from README")

    def test_every_hook_script_is_listed(self) -> None:
        hooks = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        scripts = set(re.findall(r"scripts/([\w.-]+\.sh)", json.dumps(hooks)))
        self.assertTrue(scripts, "no hook scripts found in hooks/hooks.json")
        for script in sorted(scripts):
            with self.subTest(script=script):
                self.assertIn(f"`{script}`", self.md, f"hook script {script} missing from README")

    def test_every_plugin_option_is_documented(self) -> None:
        options = json.loads(PLUGIN_JSON.read_text(encoding="utf-8")).get("userConfig", {})
        for key in sorted(options):
            with self.subTest(option=key):
                self.assertIn(f"`{key}`", self.md, f"plugin option {key} missing from README")

    def test_policy_documents_exist_and_are_linked(self) -> None:
        """Relative links, or absolute links to the file on main (which also work in the directory)."""
        for doc in (PRIVACY, SECURITY):
            with self.subTest(doc=doc.name):
                self.assertTrue(doc.is_file(), f"{doc.name} missing")
                link = rf"\]\((?:{re.escape(REPO_URL)}/blob/main/)?{re.escape(doc.name)}\)"
                self.assertRegex(self.md, link, f"README does not link {doc.name}")


class PolicyDocumentTests(unittest.TestCase):
    def test_privacy_policy_has_effective_date_and_contact(self) -> None:
        text = PRIVACY.read_text(encoding="utf-8")
        self.assertRegex(text, r"Effective date: \d{4}-\d{2}-\d{2}")
        self.assertRegex(text, r"[\w.+-]+@[\w-]+\.[\w.]+", "no contact email in PRIVACY.md")
        self.assertRegex(text, r"(?i)telemetry", "PRIVACY.md should state the telemetry position")

    def test_security_policy_explains_private_reporting(self) -> None:
        text = SECURITY.read_text(encoding="utf-8")
        self.assertIn("Report a vulnerability", text)
        self.assertRegex(text, r"[\w.+-]+@[\w-]+\.[\w.]+", "no reporting email in SECURITY.md")
        self.assertRegex(text, r"(?im)^## Supported versions")


class NoImagePathsInCodeTests(unittest.TestCase):
    def test_docs_keep_image_and_font_paths_out_of_code(self) -> None:
        pattern = image_or_font_pattern()
        for name in DOCS:
            path = ROOT / name
            if not path.is_file():
                continue
            fences, inline, _ = split_markdown(path.read_text(encoding="utf-8"))
            for snippet in fences + inline:
                m = pattern.search(snippet)
                with self.subTest(doc=name, snippet=snippet[:60]):
                    self.assertIsNone(m, f"image or font path inside code in {name}: {m.group(0) if m else ''}")


class SvgSafetyTests(unittest.TestCase):
    def test_svgs_are_static_and_self_contained(self) -> None:
        self.assertTrue(plugin_icons(), "no plugin icon (an SVG file) in the plugin metadata folder")
        for svg in svg_files():
            text = svg.read_text(encoding="utf-8")
            rel = svg.relative_to(ROOT).as_posix()
            with self.subTest(svg=rel):
                self.assertIn("<title", text, f"{rel} needs a <title> for screen readers")
                hits = [bad for bad in SVG_BAD if re.search(bad, text, re.I)]
                self.assertEqual(hits, [], f"{rel} is not static/self-contained: {hits}")


if __name__ == "__main__":
    unittest.main()
