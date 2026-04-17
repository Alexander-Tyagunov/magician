#!/usr/bin/env bash
# Displays wizard cat and injects basic project context.
# Plan 2 replaces the detection block with the full dynamic inspector.

set -euo pipefail

PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}"
mkdir -p "$PLUGIN_DATA/chronicle"

date -u +"%Y-%m-%dT%H:%M:%SZ" > "$PLUGIN_DATA/session-start-time.txt"

if [ -t 2 ] || [ "${FORCE_COLOR:-}" = "1" ]; then
  BLUE='\033[0;34m'; YELLOW='\033[0;33m'; GREEN='\033[0;32m'
  PURPLE='\033[0;35m'; RED='\033[0;31m'; CYAN='\033[0;36m'
  RESET='\033[0m'
else
  BLUE=''; YELLOW=''; GREEN=''; PURPLE=''; RED=''; CYAN=''; RESET=''
fi

cat >&2 <<CAT

${BLUE}         *        ${RESET}
${BLUE}        /|\\       ${RESET}
${BLUE}       / | \\      ${RESET}
${BLUE}      /  ⚽  \\     ${RESET}
${BLUE}     /_________\\  ${RESET}
${BLUE}    /\\${RESET}  ◉    ◉  ${BLUE}/\\${RESET}${CYAN}────${RESET}🪄 ${YELLOW}✦${RESET}${GREEN}˚${RESET}${CYAN}·${RESET}${PURPLE}✧${RESET}${RED}˚${RESET}${YELLOW}·✦${RESET}${GREEN}˚${RESET}${PURPLE}·✧${RESET}
${BLUE}   /    ═══════   \\${RESET}${CYAN}    ˚·${RESET}${YELLOW}✦${RESET}${PURPLE}·˚·${RESET}${GREEN}✧${RESET}${RED}·˚·${RESET}${YELLOW}✦${RESET}
${BLUE}  /    ( ~~~~~)    \\${RESET}${PURPLE}  ✧${RESET}${CYAN}˚·${RESET}${YELLOW}✦${RESET}${GREEN}˚·${RESET}${RED}✧${RESET}${YELLOW}˚·${RESET}${PURPLE}✦${RESET}
${BLUE}  \\________________/${RESET}
${BLUE}     |   | |   |  ${RESET}

CAT

ARCHETYPE="unknown"
TECHS=""
LORE_NOTE=""

detect_append() { TECHS="${TECHS:+$TECHS, }$1"; }

[ -f "package.json" ]     && { detect_append "javascript"; ARCHETYPE="web"; }
[ -f "tsconfig.json" ]    && detect_append "typescript"
[ -f "pom.xml" ]          && { detect_append "java"; ARCHETYPE="backend"; }
[ -f "build.gradle" ]     && { detect_append "jvm"; ARCHETYPE="backend"; }
[ -f "go.mod" ]           && { detect_append "go"; ARCHETYPE="backend"; }
[ -f "Cargo.toml" ]       && { detect_append "rust"; ARCHETYPE="backend"; }
[ -f "pubspec.yaml" ]     && { detect_append "flutter"; ARCHETYPE="mobile"; }
[ -f "project.godot" ]    && { detect_append "godot"; ARCHETYPE="gamedev"; }
[ -d "Assets" ] && [ -d "ProjectSettings" ] && { detect_append "unity"; ARCHETYPE="gamedev"; }

if [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then
  detect_append "python"; ARCHETYPE="backend"
fi

if [ -n "$TECHS" ]; then
  LORE_NOTE="Detected stack: $TECHS. Archetype: $ARCHETYPE."
else
  LORE_NOTE="No stack markers found. Run /almanac to initialize workspace."
fi

CHRONICLE_NOTE=""
LATEST_CHRONICLE=$(ls -t "$PLUGIN_DATA/chronicle/"*.json 2>/dev/null | head -1 || true)
if [ -n "$LATEST_CHRONICLE" ]; then
  SUMMARY=$(python3 -c "
import json, sys
try:
    d = json.load(open('$LATEST_CHRONICLE'))
    print(d.get('summary', ''))
except: pass
" 2>/dev/null || true)
  [ -n "$SUMMARY" ] && CHRONICLE_NOTE=" Last session: $SUMMARY"
fi

STRATEGY_NOTE=""
STRATEGY_FILE="$PLUGIN_DATA/workspace-strategy.json"
if [ -f ".gitignore" ] && [ -f "$STRATEGY_FILE" ]; then
  CURRENT_IGNORED=$(grep -c "\.workspace" .gitignore 2>/dev/null || echo "0")
  STORED=$(python3 -c "
import json
try:
    d = json.load(open('$STRATEGY_FILE'))
    print(d.get('ignored', 'unknown'))
except: print('unknown')
" 2>/dev/null)
  if [ "$CURRENT_IGNORED" = "0" ] && [ "$STORED" = "true" ]; then
    STRATEGY_NOTE=" NOTE: .workspace/ is no longer gitignored — workspace strategy may have changed. Please confirm with user whether to switch to shared mode."
  elif [ "$CURRENT_IGNORED" != "0" ] && [ "$STORED" = "false" ]; then
    STRATEGY_NOTE=" NOTE: .workspace/ is now gitignored — workspace strategy may have changed. Please confirm with user whether to switch to private mode."
  fi
fi

CONTEXT="${LORE_NOTE}${CHRONICLE_NOTE}${STRATEGY_NOTE}"
python3 -c "import json, sys; print(json.dumps({'additionalContext': sys.argv[1]}))" "$CONTEXT"
