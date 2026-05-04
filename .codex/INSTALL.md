# Installing Magician for Codex

Enable Magician in Codex through the native plugin system. Magician ships Codex-specific adapter skills under `.codex-plugin/skills/` so Codex can use the same SDLC workflows without modifying Claude Code setup.

## Prerequisites

- Codex CLI or Codex app with plugin support
- Git, if installing from GitHub or a cloned checkout

## Recommended Installation

Add the Magician plugin source:

```bash
codex plugin marketplace add Alexander-Tyagunov/magician
```

Restart Codex after adding the source. In the Codex app, open Plugins and enable Magician.

If Magician does not appear in the Plugins UI after adding the marketplace, add this block to `~/.codex/config.toml`:

```toml
[plugins."magician@magician"]
enabled = true
```

Restart Codex or start a new Codex thread after enabling the plugin. Codex loads plugins at session startup, so an already-open thread may not show newly enabled skills.

## Local Checkout Installation

Use this while developing Magician or testing an unmerged branch:

```bash
git clone https://github.com/Alexander-Tyagunov/magician.git ~/.codex/magician
codex plugin marketplace add ~/.codex/magician
```

If you already have this repository checked out locally, add that directory instead:

```bash
codex plugin marketplace add /absolute/path/to/magician
```

## Verify

Start a new Codex session and ask:

```text
Set up Magician in this workspace.
```

Codex should load the `almanac` adapter skill from `.codex-plugin/skills/almanac/SKILL.md`. A local checkout should contain 21 Codex adapter skills:

```bash
find ~/.codex/magician/.codex-plugin/skills -name SKILL.md | wc -l
```

## Design Capabilities

Magician includes a free local design companion through `/conjure`. It starts a Node.js localhost server, writes design screens under `.workspace/shared/...`, opens them in Codex Browser Use, records click feedback, and iterates until the design is approved.

For this built-in path you need:

- Node.js available on `PATH`
- Codex Browser Use enabled

No Figma or external design SaaS is required for the Magician design loop.

Optional: install OpenAI's official Build Web Apps plugin when you want extra Codex-native help with frontend implementation, UI review, React/Next.js guidance, or deployment-related web app work:

```bash
npx codex-marketplace add openai/plugins/plugins/build-web-apps --plugin
```

Optional: use the Figma plugin only when your workflow starts from, or needs to write back to, Figma. Figma is external/proprietary and is not required for Magician parity:

```bash
npx codex-marketplace add openai/plugins/plugins/figma --plugin
```

## Updating

If installed from GitHub:

```bash
codex plugin marketplace upgrade magician
```

If installed from a local checkout:

```bash
cd ~/.codex/magician
git pull
```

## Uninstalling

Remove the configured plugin source:

```bash
codex plugin marketplace remove magician
```

If you cloned Magician only for Codex, you can also remove the checkout:

```bash
rm -rf ~/.codex/magician
```

## Notes

- Do not symlink the raw `skills/` directory into `~/.agents/skills/`. That bypasses Magician's Codex adapter layer.
- Codex loads adapter skills from `.codex-plugin/skills/`; those adapters read the original source skills and translate Claude Code-specific instructions to Codex behavior.
- Claude Code is unaffected by this installation path. Claude continues to use `.claude-plugin/`, `hooks/`, `settings.json`, and the source `skills/` directory.
