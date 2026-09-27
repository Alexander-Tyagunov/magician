# magician — `codex-plugin` branch

This orphan branch holds everything Codex-specific for magician and the **generated, committed**
Codex package that Codex users install. The Claude Code plugin — source skills, lore, bundled CLIs,
the release version — lives on `main`, which is the single source of truth. Main never references
this branch's code; its `.agents/plugins/marketplace.json` only points Codex here:

```json
{"source": "git-subdir", "url": "https://github.com/Alexander-Tyagunov/magician.git",
 "path": "./plugins/magician", "ref": "codex-plugin"}
```

Do not delete or force-push this branch: every Codex install resolves it.

## Layout

| Path | What it is |
| --- | --- |
| `plugins/magician/` | **Generated** Codex package (what Codex installs). Never edit by hand; rebuild it. |
| `.codex-plugin/plugin.json` | Codex manifest template (no `version`; the build injects main's). |
| `.codex-plugin/skills/` | 26 Codex adapter skills (25 wrap main's skills, `project-context` is Codex-only). |
| `.codex-plugin/references/codex-adapter.md` | Shared Codex adapter rules every adapter reads first. |
| `.codex-plugin/lore/` | Codex overlays for main's `lore/models.md` and `lore/model-behavior.md`. |
| `.codex-plugin/scripts/build_package.py` | Builds `plugins/magician` from a main checkout. |
| `.codex-plugin/scripts/gate.sh` | Branch gate: package == build(main@SOURCE_REF), then `tests/codex`. |
| `.codex-plugin/scripts/smoke-install.sh` | Installs the package into throwaway `CODEX_HOME`s (never `~/.codex`). |
| `.codex-plugin/SOURCE_REF` | The main commit/tag the committed package was built from. |
| `hooks/codex-hooks.json`, `scripts/codex-*` | Codex destructive-command guard (`PreToolUse`). |
| `tests/codex/` | Package, adapter, detector and guard tests (need `MAGICIAN_MAIN_SOURCE`). |
| `.agents/plugins/marketplace.json` | Local dev marketplace pointing at `./plugins/magician`. |
| `INSTALL.md` | End-user install, update and credential guide. |

## Install / update (end users)

```bash
codex plugin marketplace add Alexander-Tyagunov/magician --sparse .agents/plugins
codex plugin add magician@magician

# update
codex plugin marketplace upgrade magician
codex plugin add magician@magician
```

See [INSTALL.md](INSTALL.md) for hook trust, credentials and environment-policy notes.

## Main → Codex contract

The build (`build_package.py --source <main> [--ref <ref>]`) consumes only `skills/`, `lore/`,
`bin/`, `LICENSE` and `.claude-plugin/plugin.json` from main. Every rewrite anchor below is
mandatory: if main drifts, the build fails loudly instead of shipping Claude-only behavior.

- **Version**: `.claude-plugin/plugin.json` `version` (X.Y.Z) is injected into the Codex manifest.
- **Bins**: an allowlist. `jira`, `confluence`, `kg`, `ctx` and `magician-scan` ship; `magician-ui` and
  `magician-statusline` (Claude settings/status line) are excluded. Any other file in main's `bin/`
  fails the build until it is classified in `build_package.py`.
- **Credentials** (`bin/jira`, `bin/confluence`): exactly one block between
  `# ---- magician:connection-config begin` and `# ---- magician:connection-config end ----`.
  Inside it, every setting is read only as `os.environ.get("CLAUDE_PLUGIN_OPTION_<KEY>")`, and the
  block has exactly one top-level assignment each of `CONFIG_LOADED`, `SETUP_HINT` and
  `BASE_URL_HINT`. The build maps keys to Codex environment names
  (`JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`→`JIRA_API_TOKEN|JIRA_PAT|JIRA_PROD_PAT`, and the
  same for `CONFLUENCE_*`), fails on any unknown key, replaces the three assignments with Codex
  text (dropping `CONFIG_LOADED` and main's one "settings aren't loaded" branch), drops Claude-only
  comment paragraphs, and asserts that no `CLAUDE_PLUGIN_OPTION_`,
  `/plugin configure`, `userConfig` or `MAGICIAN_USERCONFIG_BRIDGE` text remains and that the auth
  header still goes to curl on stdin (`"-H", "@-"` with `input=headers`), checked on the parsed
  code: no curl argv element may reference the token, the email, the auth helper or an auth literal.
- **State paths** (Codex root: `$MAGICIAN_HOME`, else `$CODEX_HOME/magician`, else `~/.codex/magician`):

  | File | Required anchors |
  | --- | --- |
  | `bin/jira`, `bin/confluence` | the two-line `# Cache/pacing dir: MAGICIAN_DATA …` comment; the `PLUGIN_DATA = os.environ.get("CLAUDE_PLUGIN_DATA") or …` line followed by `PLUGIN_DATA = os.environ.get("MAGICIAN_DATA") or PLUGIN_DATA` |
  | `bin/kg` | `${MAGICIAN_HOME:-$HOME/.claude/magician}` (docstring); `MAGICIAN_HOME = os.environ.get("MAGICIAN_HOME") or os.path.join(HOME, ".claude", "magician")` |
  | `bin/ctx` | `Data directory: $MAGICIAN_DATA, else $CLAUDE_PLUGIN_DATA, else ~/.local/share/magician.`; the two-line `PLUGIN_DATA = (os.environ.get("MAGICIAN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA") …)` |

- **Lore**: main's lore is `lore/<tech>.md` cores plus `lore/deep/<tech>.md` with `##` sections
  carrying explicit `<a id="…"></a>` anchors; `project-context` recommends
  `lore/deep/<tech>.md#<anchor>` sections. The overlays must keep every anchor main links to (for
  example `models.md#safety-classifiers-change-which-model-you-end-up-on`).
- **Skills**: the adapter set must equal main's skill set plus `project-context`.

## Release runbook (every main release)

Rule: `codex-plugin` must exist on `origin` whenever main's marketplace entry points at it, and the
commit in `.codex-plugin/SOURCE_REF` must be reachable from `origin` (CI exports it from a clone).
The build needs Python 3.9+ and git.

### First release on this branch (v4.15.0)

v4.15.0 is the release that points main's marketplace entry at this branch, so the order matters:

1. Push main's release branch unchanged, so the commit in `.codex-plugin/SOURCE_REF` resolves on
   `origin` (or rebuild from the pushed head with `--ref` and update `SOURCE_REF`, then gate and
   commit).
2. `git push -u origin codex-plugin` **before** main's release PR merges; otherwise Codex installs
   fail with a missing `codex-plugin` ref.
3. After the merge and the `v4.15.0` tag, follow the steps below with `vX.Y.Z = v4.15.0`, so
   `SOURCE_REF` names the tag instead of a pre-merge commit.

### Every later release

After main's release is merged and tagged `vX.Y.Z`:

```bash
git -C ~/IdeaProjects/magician fetch origin --tags
cd ~/IdeaProjects/magician-codex && git switch codex-plugin && git pull --ff-only origin codex-plugin
python3 .codex-plugin/scripts/build_package.py --source ~/IdeaProjects/magician --ref vX.Y.Z
printf 'vX.Y.Z\n' > .codex-plugin/SOURCE_REF
bash .codex-plugin/scripts/gate.sh ~/IdeaProjects/magician
git add plugins/magician .codex-plugin/SOURCE_REF   # plus any adapter/build edits you made
git commit -m "codex: package vX.Y.Z" -m "Source-Main: $(git -C ~/IdeaProjects/magician rev-parse 'vX.Y.Z^{commit}')"
MAGICIAN_CODEX_SMOKE=1 bash .codex-plugin/scripts/gate.sh ~/IdeaProjects/magician   # after the commit
git push origin codex-plugin
```

The smoke tier installs the committed package through main's real git-subdir entry, so it runs after
the commit (it refuses to run while `plugins/magician` has uncommitted changes) and before the push.
Always build release packages with `--ref` so untracked working-tree files never leak into the
package. If main changed a skill, review the matching adapter; if main changed an anchor above,
update `build_package.py` and this table together. After the first release, forgetting a release
leaves Codex users on the previous package; nothing breaks.

CI (`.github/workflows/codex-gate.yml`) runs the gate on pushes and pull requests to this branch,
against a full-history checkout of `main`.
