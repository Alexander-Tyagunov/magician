#!/usr/bin/env bash
# Install the codex package into throwaway CODEX_HOMEs. Never touches ~/.codex.
# Temp homes are left in $TMPDIR for inspection (no destructive cleanup).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CODEX_BIN="${CODEX_BIN:-$(command -v codex || true)}"
for c in /Applications/ChatGPT.app/Contents/Resources/codex /Applications/Codex.app/Contents/Resources/codex; do
  if [ -z "$CODEX_BIN" ] && [ -x "$c" ]; then CODEX_BIN="$c"; fi
done
[ -n "$CODEX_BIN" ] || { echo "smoke: no codex CLI found; skipping"; exit 0; }

# Every codex start (even --version) writes helpers under its CODEX_HOME, so each call goes through
# this wrapper, which refuses to run unless CODEX_HOME is a fresh throwaway home outside ~/.codex.
fresh_home() { mktemp -d "${TMPDIR:-/tmp}/magician-codex-home.XXXXXX"; }
codex_isolated() {
  local home real_home
  home="${CODEX_HOME:-}"
  [ -n "$home" ] && [ -d "$home" ] || { echo "smoke: refusing to run codex without a throwaway CODEX_HOME" >&2; exit 1; }
  home="$(cd "$home" && pwd -P)"
  real_home="$(cd "$HOME" && pwd -P)"
  case "$home/" in
    "$real_home/.codex/"*) echo "smoke: refusing to run codex with CODEX_HOME under ~/.codex" >&2; exit 1 ;;
  esac
  "$CODEX_BIN" "$@"
}
unset CODEX_HOME
export CODEX_HOME="$(fresh_home)"
echo "smoke: using $(codex_isolated --version 2>/dev/null || echo "$CODEX_BIN")"

# Implicitly invocable adapters = all adapters minus those whose policy disables implicit invocation.
total="$(find "$ROOT/.codex-plugin/skills" -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l | tr -d ' ')"
explicit="$(grep -l 'allow_implicit_invocation: false' "$ROOT"/.codex-plugin/skills/*/agents/openai.yaml 2>/dev/null | wc -l | tr -d ' ')"
expected=$((total - explicit))

# 1) codex-plugin branch dev marketplace (local source) -> exact package, skills visible
export CODEX_HOME="$(fresh_home)"
codex_isolated plugin marketplace add "$ROOT" >/dev/null
codex_isolated plugin add magician@magician >/dev/null
INSTALLED="$(ls -d "$CODEX_HOME"/plugins/cache/magician/magician/*/ | head -n 1)"
diff -r "$ROOT/plugins/magician" "$INSTALLED"
visible="$(codex_isolated debug prompt-input hi | grep -o 'magician:[a-z-]*' | sort -u | wc -l | tr -d ' ')"
[ "$visible" -eq "$expected" ] || { echo "smoke: expected $expected implicit magician skills, got $visible"; exit 1; }
echo "smoke: local package installs byte-identical; $visible implicit skills visible"

# 2) main's real git-subdir entry, resolved against the LOCAL repo's committed codex-plugin ref
#    (no network, no push). Tests the COMMITTED package, so run it after committing the rebuild.
if [ -n "${MAGICIAN_MAIN_SOURCE:-}" ]; then
  if ! git -C "$ROOT" diff --quiet codex-plugin -- plugins/magician \
     || [ -n "$(git -C "$ROOT" ls-files --others --exclude-standard -- plugins/magician)" ]; then
    echo "smoke: working-tree plugins/magician differs from committed codex-plugin; commit it, then rerun" >&2
    exit 1
  fi
  M="$(mktemp -d "${TMPDIR:-/tmp}/magician-mkt.XXXXXX")"; mkdir -p "$M/.agents/plugins"
  GITDIR="$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir)"
  sed "s#\"url\": *\"[^\"]*\"#\"url\": \"file://$GITDIR\"#" \
    "$MAGICIAN_MAIN_SOURCE/.agents/plugins/marketplace.json" > "$M/.agents/plugins/marketplace.json"
  export CODEX_HOME="$(fresh_home)"
  codex_isolated plugin marketplace add "$M" >/dev/null
  codex_isolated plugin add magician@magician >/dev/null
  INSTALLED="$(ls -d "$CODEX_HOME"/plugins/cache/magician/magician/*/ | head -n 1)"
  diff -r <(git -C "$ROOT" ls-tree -r --name-only codex-plugin -- plugins/magician | sed 's#^plugins/magician/##' | sort) \
          <(cd "$INSTALLED" && find . -type f | sed 's#^\./##' | sort)
  echo "smoke: main git-subdir entry resolves against committed codex-plugin ref"
fi
echo "smoke OK"
