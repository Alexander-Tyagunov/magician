# Screenshots as evidence — capture and diff

Shared by `/conjure` (approved designs), `/certify` (the UI check) and `/transmute` (parity golden captures). A screenshot here is evidence that a person or a later skill can open, not decoration. It has a fixed name, a fixed place, and a diff against the previous version.

## Where

`.workspace/local/screens/<feature>/v<n>/<theme>-<viewport>.png`

- `<feature>` — the design or change name. For conjure it is the `<feature>` of `<design-dir>`. For certify it is the branch or task name.
- `v<n>` — the design or build version being captured. A new round of changes gets `v<n+1>`, never an overwrite.
- `<theme>` — `light` or `dark`. Capture both whenever the page has a theme toggle or a `[data-theme]` attribute, else `light` only.
- `<viewport>` — one of `phone` (390×844), `tablet` (834×1194), `desktop` (1440×900), `wide` (1920×1080). Capture every viewport the user chose at GATE 3 step 2 (default `phone` + `desktop`). When no choice was made, capture `desktop` only.

`.workspace/local/` is gitignored, so the PNGs stay on this machine. The approved HTML stays in `<design-dir>/screens/v<n>/` as the durable, committed design artifact. A screenshot that must travel with the spec is copied next to it as `<design-dir>/screens/v<n>/<theme>-<viewport>.png` and linked from the spec.

## How (Playwright MCP)

With the Playwright MCP server available (`mcp__playwright__*` tools), do this per viewport and per theme:

1. `mcp__playwright__browser_resize({ width, height })` for the viewport.
2. `mcp__playwright__browser_navigate({ url })`. The URL is the companion page (`<url-base>/v<n>/mockup.html`), the dev server page for certify, or a `file://` path to the HTML pair.
3. Switch the theme: `mcp__playwright__browser_evaluate({ function: "() => document.documentElement.setAttribute('data-theme', 'dark')" })`, or click the page's toggle. Skip this for `light` when it is the default.
4. `mcp__playwright__browser_wait_for({ time: 800 })` so Mermaid, fonts and entrance animations settle.
5. `mcp__playwright__browser_take_screenshot({ filename: ".workspace/local/screens/<feature>/v<n>/<theme>-<viewport>.png", fullPage: true })`.

`/conjure` pre-approves only `browser_take_screenshot`, `browser_snapshot`, `browser_wait_for` and `browser_close`. The navigate, resize and evaluate calls go through Claude Code's normal permission prompt. Without a Playwright MCP server, say so. Then ask the user to screenshot the page into the same path, or skip the capture and write "no screenshot (Playwright unavailable)" where the paths would go. Never install Playwright for this.

## Attach the paths

Every Completion Signal that reports a captured screen lists the PNG paths on one line, comma-separated, so the next skill can open them. This applies to conjure's signal after an approved mockup, certify's evidence summary after the UI check, and transmute's parity report. A path is evidence only when the file exists at the moment of the claim. Check with Glob before you list it.

## Diff v<n> against v<n+1>

When a later version of the same screen exists, run the bundled diff before the user reviews the new version. A tool then catches an unintended change (a shifted margin, a lost dark-theme token) that the eye misses:

```bash
node ${CLAUDE_SKILL_DIR}/scripts/screen-diff.cjs .workspace/local/screens/<feature>/v1 .workspace/local/screens/<feature>/v2
```

`${CLAUDE_SKILL_DIR}` is `skills/conjure` under the plugin root. From certify or transmute, write the plugin-root path `${CLAUDE_PLUGIN_ROOT}/skills/conjure/scripts/screen-diff.cjs`. No skill pre-approves `node`, so the command goes through the normal permission prompt.

The script compares every same-named PNG pixel by pixel. It looks for `playwright` or `playwright-core` in the project, then in a global install (the npm global folder, or the folder of a `playwright` command on `PATH`). When it finds one, it uses Playwright's own image comparator (the one behind `toHaveScreenshot`). It then writes `<name>.diff.png` next to the newer version (`v2/diff/`) with the changed pixels highlighted. Without Playwright, it decodes the PNGs with the standard library and counts the differing pixels. No diff image then.

Options: `--max-ratio` (default `0.001`, the share of pixels allowed to differ), `--threshold` (per-channel tolerance, default `0.2`), `--out`, `--engine` (`auto`, `playwright` or `stdlib`, default `auto`), `--json`. Exit 0 means every shared screenshot is within the ratio. Exit 1 lists the changed ones. Exit 2 is a usage error. Nothing is installed. `pixelmatch` is not needed.

Report the result in two lines. First, which screens changed, with the percentage. Second, whether each change was intended (the user asked for it) or not. An unintended change goes back to the design before the next gate.
