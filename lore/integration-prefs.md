# Integration preferences — opt-out memory

Some users don't use a given integration (Jira, Confluence, …) and don't want to be asked about it. Respect that: once a user says they don't have it, or declines setup with "don't ask again", **stop proactively suggesting it**.

## Store

`${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}/integration-prefs.json`

```json
{ "jira": "disabled", "confluence": "disabled" }
```
A key set to `"disabled"` = the user opted out. Absent key = ask normally. Read it:
```bash
PREFS="${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}/integration-prefs.json"
state=$(jq -r '.jira // "ask"' "$PREFS" 2>/dev/null || echo ask)   # "disabled" | "ask"
```
Write it (merge, don't clobber other keys):
```bash
mkdir -p "$(dirname "$PREFS")"
tmp=$(jq -c '. + {"jira":"disabled"}' "$PREFS" 2>/dev/null || echo '{"jira":"disabled"}'); printf '%s\n' "$tmp" > "$PREFS"
```

## Rules

- **Record an opt-out** when the user says they don't use a service ("I don't have Jira", "we don't use Confluence", "skip the integration"), or declines setup with *don't ask again*: set that key to `"disabled"`. Say so briefly ("Noted — I won't bring up Jira again unless you ask.").
- **Proactive suggestions** (from `/magic`, `/divine`, or any dependent skill): if the key is `"disabled"`, do **not** suggest setting it up or using it. Stay silent and use other sources.
- **Direct requests override.** If the user directly invokes the skill or asks to use the service ("check jira", `/magician:jira`, "set up confluence"), honor it — that *is* them asking again. Proceed with setup/use and **clear** the `"disabled"` flag (`jq 'del(.jira)'`), since they now want it.
- Opt-out is per service, and reversible at any time by the user asking for it.
