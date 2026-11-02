# almanac — optional extras (step 9)

Step 9 of [`../SKILL.md`](../SKILL.md) offers three extras. Write only the ones the user selects. Never overwrite a file that exists. Never install a hook or change a settings file: magician writes no user settings.

## North star

Write `.workspace/shared/north-star.md` with one paragraph of 120 words or fewer. Ask the user for it, or draft it from the README and let the user correct it. The paragraph says what the project is for, who it serves, and the one outcome that shows it works.

```markdown
# North star

<One paragraph: what this project is for, who it serves, and the one outcome that shows it works.>
```

`/manifest` Phase 0 and `/conjure` read this file when it exists. The spec carries one line, `**North star:** fits` or `**North star:** conflicts because <reason>`.

## Production-gate hook (template only)

A skill is advisory. A rule that must hold every time needs a hook ([`lore/skill-authoring.md`](../../../lore/skill-authoring.md#advisory-vs-enforced)). Write the template below to `.workspace/shared/hooks/production-gate.sh`. Without `RELEASE_APPROVAL` it blocks a Bash deploy command that targets production. It also blocks a deploy command that hides its words: a backslash, joined quotes, a `$` variable or substitution, a backtick, `bash -c`, `sh -c` or `eval`. It fails closed: input over 64 KiB, or input it cannot read, is blocked. A deploy is a deploy word as the command word of a segment, so `cat deploy/prod.yaml` passes. Tell the user five things:
1. The file is a template. It is not active until the user adds the settings snippet below.
2. The template is a guard rail against honest mistakes, not a security boundary. A determined agent can get around a text match. Real enforcement is server-side: protected environments and required reviewers on the deploy target.
3. The patterns at the top need the project's own deploy tools and environment names.
4. A human sets `RELEASE_APPROVAL` (for example to a ticket or change id) before starting the session that deploys.
5. The hook runs in the project directory. Use an absolute path in the snippet if sessions start elsewhere.

```bash
#!/usr/bin/env bash
# production-gate.sh: PreToolUse(Bash) hook TEMPLATE written by magician /almanac. Not installed.
# A guard rail against honest mistakes, not a security boundary: real enforcement is server-side
# (protected environments, required reviewers). Without RELEASE_APPROVAL it blocks a deploy command
# that targets production, and a deploy command that hides its words. Fails closed on input it
# cannot read. Exit 2 blocks the tool call before permission rules apply. Plain bash 3.2.
export LC_ALL=C
[ -n "${RELEASE_APPROVAL:-}" ] && exit 0
block() { echo "production-gate: $1 needs RELEASE_APPROVAL, set by a human before the session starts." >&2; exit 2; }
# Edit these patterns for this project's deploy tools and environment names.
WORD='^(deploy|release|promote)([:._-][a-z0-9:._-]*)?$'     # a deploy word as a command word
PAIR='^(helm (upgrade|install)|kubectl (apply|rollout)|terraform apply|gh workflow)$'
PROD='(^|[^a-z])(prod|prd|production)([^a-z]|$)'
QJOIN="[a-z0-9][\"'][a-z0-9]"                                 # pro"d", dep'loy
NEST='(^|[^a-z])((ba|z)?sh -c|eval)([^a-z]|$)'

[ -t 0 ] && block "a call without hook input"
INPUT=$(head -c 65537)
[ ${#INPUT} -le 65536 ] || block "a hook input over 64 KiB"
INPUT=$(printf '%s' "$INPUT" | tr -d '\n\r')
re='"command"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)"'
[[ $INPUT =~ $re ]] || block "a hook input without a readable command"
# Decode the JSON string: \\ -> @bs@ (a real backslash), \" -> ", \n -> ; (a new command).
CMD=$(printf '%s' "${BASH_REMATCH[1]}" | sed -e 's/\\\\/@BS@/g' -e 's/\\"/"/g' -e 's/\\[nr]/;/g' \
  -e 's/\\[tbf]/ /g' -e 's,\\/,/,g' | tr '[:upper:]' '[:lower:]')
case "$CMD" in *'\'*) block "a command with \\u escapes" ;; esac
FLAT=$(printf '%s' "$CMD" | sed 's/@bs@//g' | tr -d "\"'")     # dep''loy -> deploy, pro\d -> prod

is_deploy() {   # a segment whose command word (after VAR=x, sudo, bash -c, npm run ...) deploys
  local seg
  while IFS= read -r seg; do
    set -f; set -- $seg; set +f
    while [ $# -gt 0 ]; do
      case "$1" in
        *=*|sudo|env|time|nohup|exec|command|eval|bash|sh|zsh|-c) shift ;;
        npm|pnpm|yarn|bun) shift; [ "${1:-}" = run ] && shift ;;
        *) break ;;
      esac
    done
    [ $# -gt 0 ] || continue
    if [[ ${1##*/} =~ $WORD ]] || [[ ${2:-} =~ $WORD ]] || [[ "$1 ${2:-}" =~ $PAIR ]]; then return 0; fi
  done <<EOF
$(printf '%s' "$FLAT" | tr ';&|()`' '\n\n\n\n\n\n')
EOF
  return 1
}

is_deploy || exit 0
[[ $FLAT =~ $PROD ]] && block "a production deploy"
case "$CMD" in *@bs@*|*'$'*|*'`'*|*'""'*|*"''"*) block "a deploy command with escapes, variables or substitutions" ;; esac
[[ $CMD =~ $QJOIN ]] && block "a deploy command with joined quotes"
[[ $CMD =~ $NEST ]] && block "a deploy command in a nested shell"
exit 0
```

Settings snippet for the user to paste into `.claude/settings.json` (or to add through `/hooks`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "bash .workspace/shared/hooks/production-gate.sh" }]
      }
    ]
  }
}
```

On Codex, local hooks live in `hooks.json` under `<repo>/.codex/`, use the same event names, block with exit 2, and need trust through `/hooks`.

## Cost attribution

Print these hints in chat and write nothing:
- The agent exports OpenTelemetry metrics, cost and tokens included, when the user turns on its telemetry setting. Set `OTEL_RESOURCE_ATTRIBUTES` (for example `team=payments,project=<repo>`) so the cost of each team and project shows up as its own series.
- `claude plugin details magician` prints magician's always-on token cost and the cost of each skill when invoked.
- `/weave` and `/orchestrate` report the session cost delta in their completion line when a cost source is available: the file `~/.claude/magician/status/<session id>.cost` (`$MAGICIAN_HOME/status/` when that is set), which the magician status line writes from the cost Claude Code passes it, or the status band of the experimental mod. With neither, they omit the cost. They never estimate it.
