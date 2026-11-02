"""plan.html design self-test — the acquired design principles checked by code, not by eye.

The walkthrough page `tools/plan-render` emits is held to lore/deep/design-principles.md: WCAG AA
contrast for every text token on the canvas and the surface in both themes (and 3:1 for the control
boundary line), 44 px hit areas on every button, a prefers-reduced-motion block, a visible
`:focus-visible` style, and a `<title>`, `<desc>` and a screen-reader data table for every chart.
Tokens are parsed out of the template in the tool source, so a palette change that breaks contrast
fails here before it ships. The live-loop additions are held to the same contract: the revising ring
is a `role="status"` live region inside an `aria-busy` card, notices from the session land in a
visually-hidden live region that is announced even while the helper panel is closed, and every
control that must not fire during a revision (or in a read-only artifact view) is `disabled`, not
merely greyed.
"""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "plan-render"
SRC = TOOL.read_text(encoding="utf-8")
FIXTURE = ROOT / "tests" / "claude" / "fixtures" / "plans" / "valid.json"

TEXT_TOKENS = ("ink", "ink-2", "ink-3", "accent", "ok", "warn", "stop")
BACKGROUNDS = ("canvas", "surface")


def tokens(theme: str) -> dict[str, str]:
    m = re.search(r'\[data-theme="%s"\]\{(.*?)\}' % theme, SRC, re.S)
    assert m, f"no token map for theme {theme}"
    return {k: v for k, v in re.findall(r"--([\w-]+):(#[0-9A-Fa-f]{6})", m.group(1))}


def luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def rendered() -> str:
    return subprocess.run([sys.executable, str(TOOL), "html", str(FIXTURE)], capture_output=True,
                          text=True, timeout=120, check=True).stdout


class ContrastTests(unittest.TestCase):
    def test_text_tokens_reach_aa_on_canvas_and_surface_in_both_themes(self) -> None:
        for theme in ("light", "dark"):
            t = tokens(theme)
            for fg in TEXT_TOKENS:
                for bg in BACKGROUNDS:
                    with self.subTest(theme=theme, fg=fg, bg=bg):
                        self.assertGreaterEqual(contrast(t[fg], t[bg]), 4.5,
                                                f"--{fg} {t[fg]} on --{bg} {t[bg]} ({theme})")

    def test_on_accent_reaches_aa_on_accent(self) -> None:
        for theme in ("light", "dark"):
            t = tokens(theme)
            with self.subTest(theme=theme):
                self.assertGreaterEqual(contrast(t["on-accent"], t["accent"]), 4.5)

    def test_control_boundary_line_reaches_3_to_1_on_surface(self) -> None:
        for theme in ("light", "dark"):
            t = tokens(theme)
            with self.subTest(theme=theme):
                self.assertGreaterEqual(contrast(t["line"], t["surface"]), 3.0, f"--line {t['line']} ({theme})")
                self.assertGreaterEqual(contrast(t["line"], t["canvas"]), 3.0)

    def test_both_themes_define_the_same_tokens(self) -> None:
        light, dark = tokens("light"), tokens("dark")
        self.assertEqual(sorted(light), sorted(dark), "dark is the same design with a second value map")
        for name in ("canvas", "surface", "surface-2", "ink", "ink-2", "ink-3", "accent", "on-accent", "ok",
                     "warn", "stop", "line", "line-soft", "l-1", "l-2", "l-3", "l-4", "l-5", "l-6"):
            self.assertIn(name, light)

    def test_contrast_formula_self_check(self) -> None:
        self.assertAlmostEqual(contrast("#000000", "#FFFFFF"), 21.0, places=1)
        self.assertAlmostEqual(contrast("#777777", "#FFFFFF"), 4.48, places=2)


class TargetsAndMotionTests(unittest.TestCase):
    def test_buttons_have_44px_hit_areas(self) -> None:
        m = re.search(r"\n\.btn\{([^}]*)\}", SRC)
        self.assertIsNotNone(m)
        rule = m.group(1)
        for prop in ("min-height", "min-width"):
            v = re.search(prop + r":(\d+)px", rule)
            self.assertIsNotNone(v, f".btn lacks {prop}")
            self.assertGreaterEqual(int(v.group(1)), 44)
        tl = re.search(r"\n\.tl\{([^}]*)\}", SRC).group(1)
        self.assertRegex(tl, r"min-height:(4[4-9]|[5-9]\d)px")
        fab = re.search(r"\n\.helper-fab\{([^}]*)\}", SRC).group(1)
        self.assertRegex(fab, r"width:5[6-9]px;height:5[6-9]px")

    def test_reduced_motion_block_and_duration_tokens(self) -> None:
        self.assertRegex(SRC, r"@media \(prefers-reduced-motion:\s*reduce\)\{\*\{transition:none!important;animation:none!important\}")
        for tok in ("--dur-fast:120ms", "--dur-base:240ms", "--dur-slow:600ms", "--ease:cubic-bezier(.2,0,0,1)"):
            self.assertIn(tok, SRC)
        self.assertIn("matchMedia('(prefers-reduced-motion: reduce)')", SRC, "the player honours reduced motion too")

    def test_focus_visible_style_exists(self) -> None:
        self.assertRegex(SRC, r":focus-visible\{outline:2px solid var\(--accent\);outline-offset:2px")

    def test_disabled_and_hover_states_exist(self) -> None:
        self.assertIn(".btn:disabled{opacity:.38", SRC)
        self.assertIn(".btn:hover{background:var(--surface-2)}", SRC)


class ChartAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = rendered()

    def test_every_chart_svg_has_a_title_and_a_sr_table_sibling(self) -> None:
        charts = re.findall(r'<div class="chart" data-chart="([^"]+)">(.*?</table>)</div>', self.html, re.S)
        self.assertGreaterEqual(len(charts), 6)
        for key, body in charts:
            with self.subTest(chart=key):
                svgs = re.findall(r"<svg\b.*?</svg>", body, re.S)
                self.assertEqual(len(svgs), 1)
                svg = svgs[0]
                self.assertRegex(svg, r'<svg[^>]*role="img"[^>]*aria-labelledby="([\w-]+)-t \1-d"')
                self.assertRegex(svg, r"<title id=\"[\w-]+-t\">[^<]+</title>")
                self.assertRegex(svg, r"<desc id=\"[\w-]+-d\">[^<]+</desc>")
                after = body.split("</svg>", 1)[1]
                self.assertTrue(after.startswith('<table class="sr"><caption>'), "data table must follow the svg")
                self.assertIn("<th>", after)
                self.assertIn("<td>", after)

    def test_map_and_wave_graph_are_labelled_images(self) -> None:
        self.assertIn('role="img" aria-labelledby="maptitle mapdesc"', self.html)
        self.assertIn('<svg class="wavegraph" viewBox="0 0 ', self.html)
        self.assertIn('aria-labelledby="wg-title wg-desc"', self.html)

    def test_series_are_distinguished_by_pattern_not_colour_alone(self) -> None:
        self.assertIn('<pattern id="hatch"', self.html)
        self.assertIn('class="bar hatch"', self.html)
        self.assertIn("stroke-dasharray", self.html)

    def test_keyboard_contract_in_the_page(self) -> None:
        self.assertIn('<a class="skip" href="#detail">Skip to step detail</a>', self.html)
        self.assertIn('aria-live="polite"', self.html)
        self.assertIn('role="dialog" aria-modal="true"', self.html)
        self.assertIn('role="group" aria-label="Components"', self.html)
        for key in ("'ArrowRight'", "'ArrowLeft'", "k==='r'", "k==='s'", "k==='a'", "k==='c'", "k==='e'",
                    "k==='d'", "k==='h'", "k==='?'"):
            self.assertIn(key, self.html)


class LiveLoopA11yTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = rendered()

    def test_revising_ring_is_a_live_region_inside_an_aria_busy_card(self) -> None:
        self.assertIn("card.setAttribute('aria-busy',busy?'true':'false')", SRC)
        self.assertIn('<div class="revising" role="status" aria-live="polite">', SRC)
        self.assertIn('<svg class="ring" viewBox="0 0 40 40" aria-hidden="true">', SRC, "the ring is decorative; the text carries the meaning")
        self.assertIn("<b>Claude is revising '+esc(s.id)+'</b>", SRC)
        self.assertIn('<span class="mono" id="elapsed">', SRC)
        self.assertRegex(SRC, r"\.ring circle\.arc\{[^}]*animation:spin 1\.2s linear infinite")
        self.assertIn(".ring circle.arc{stroke-dasharray:160 0}", SRC, "reduced motion: a static full ring, no spinner")
        self.assertIn('<div class="banner" role="status" aria-live="polite">Waiting for Claude — check the session', SRC)
        self.assertEqual(SRC.count("const WAIT_MS=600000"), 1)

    def test_notices_have_a_live_region_outside_the_helper_panel(self) -> None:
        self.assertIn('<div class="sr" id="livenote" role="status" aria-live="polite"></div>', self.html)
        self.assertIn('<div class="helper-log" id="helperlog" aria-live="polite">', self.html)
        self.assertIn("const ln=$('#livenote'); if(ln) ln.textContent=", SRC, "helperSay mirrors Claude/system lines into the hidden live region")
        self.assertIn('<div class="toast" id="toast" role="status" aria-live="polite"></div>', self.html)

    def test_controls_are_disabled_while_revising_or_read_only(self) -> None:
        self.assertIn("const off=busy||link.readOnly;", SRC)
        for act in ("approve", "change", "edit", "defer"):
            self.assertRegex(SRC, r'data-act="%s"[^>]*\'\+\(off\?\' disabled\':\'\'\)' % act, f"{act} button is disabled, not just styled")
        self.assertIn("$('#approveplan').disabled=!(PLAN.status==='in_review'||PLAN.status==='draft')||link.readOnly;", SRC)
        self.assertIn("$('#reject').disabled=link.readOnly||PLAN.status==='approved'||PLAN.status==='rejected';", SRC)
        self.assertIn("$('#helpersend').disabled=link.readOnly;", SRC)
        self.assertIn("if(s.review.status==='revising'||link.readOnly) return;", SRC, "keyboard shortcuts respect the same gate")
        self.assertIn(".btn:disabled{opacity:.38;cursor:default;pointer-events:none}", SRC)

    def test_what_changed_table_is_a_real_table_with_headers(self) -> None:
        self.assertIn('<table class="changes"><thead><tr><th>Field</th><th>v', SRC)
        self.assertIn('<th scope="row" class="mono">', SRC)
        self.assertIn('<span class="chip accent" data-badge="version">v', SRC)


if __name__ == "__main__":
    unittest.main()
