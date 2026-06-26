# Jira REST reference (direct HTTP)

Loaded on demand from [SKILL.md](SKILL.md). All calls are `curl` to the Jira REST API — no MCP. Keep each call's timeout sane (reads ~10s; writes ~30–60s).

## Auth

Two schemes; pick by deployment:

| Deployment | API base | Auth header | curl |
|---|---|---|---|
| **Cloud** (`*.atlassian.net`) | `/rest/api/3` | Basic, `email:api_token` | `-u "$JIRA_EMAIL:$TOKEN"` |
| **Server / Data Center** | `/rest/api/2` | Bearer PAT | `-H "Authorization: Bearer $TOKEN"` |

Detect: if `JIRA_EMAIL` is set → Cloud/Basic (v3); else → Server/DC/Bearer (v2). Override with `JIRA_API_VERSION` if needed. Build the auth + base once:
```bash
BASE="${JIRA_BASE_URL%/}"
TOKEN="${JIRA_API_TOKEN:-${JIRA_PAT:-${JIRA_PROD_PAT:-}}}"
if [ -n "${JIRA_EMAIL:-}" ]; then AUTH=(-u "$JIRA_EMAIL:$TOKEN"); V="${JIRA_API_VERSION:-3}";
else AUTH=(-H "Authorization: Bearer $TOKEN"); V="${JIRA_API_VERSION:-2}"; fi
api(){ curl -sS --max-time "${3:-30}" "${AUTH[@]}" -H "Accept: application/json" "$BASE/rest/api/$V/$1" ${2:+-H "Content-Type: application/json" -d "$2"}; }
```
**Never print `$TOKEN`.** Verify connectivity: `api myself` → returns your account; `401` = bad/rotated token, connection hang/refuse = network/VPN.

## Reads & JQL

- **Single issue**: `GET issue/{key}?fields=*all&maxResults=50` (comments come back in the `comment` field).
- **Search (JQL)**: `GET search?jql=<urlencoded>&maxResults=50&fields=summary,status,assignee,updated`. Always pass `maxResults` and an `ORDER BY`. URL-encode the JQL (`--data-urlencode` with `-G`).
  - My open work — `assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC`
  - Recent in a project — `project = <KEY> AND updated >= -7d ORDER BY updated DESC`
  - Text — `project = <KEY> AND text ~ "<term>" ORDER BY updated DESC`
- **Boards / sprints** (Agile API, base `/rest/agile/1.0`): `board`, `board/{id}/sprint`, `board/{id}/issue`, `sprint/{id}/issue`. Resolve "my board" from memory or `GET board?name=<team>`.
- **Field discovery**: `GET field` (custom-field ids), `GET issue/createmeta?projectKeys=<K>&expand=projects.issuetypes.fields` (allowed values per project/type), `GET priority`, `GET issueLinkType`.

## Transitions (status change)

1. `GET issue/{key}/transitions` — only workflow-allowed transitions are returned.
2. Map the target status to a returned transition id.
3. Confirm with the user: "Move `KEY` `<current>` → `<target>`?"
4. `POST issue/{key}/transitions` with `{"transition":{"id":"<id>"}}` (+ `fields` if required, e.g. `{"resolution":{"name":"Fixed"}}`).
5. Report the new status; if the target isn't offered, list what is.

## Create / update

- **Create**: `POST issue` with `{"fields":{"project":{"key":"<K>"},"summary":"…","issuetype":{"name":"Story"},"description":<desc>}}`.
  - **Server/DC (v2)**: `description` is a **wiki-markup string**.
  - **Cloud (v3)**: `description` is an **ADF document** (JSON). For simple text use `{"type":"doc","version":1,"content":[{"type":"paragraph","content":[{"type":"text","text":"…"}]}]}`, or convert Markdown to ADF.
- **Common fields**: `priority {"name":"…"}`, `labels ["…"]`, `assignee` (Cloud `{"accountId":"…"}`, Server `{"name":"<username>"}`), `components [{"name":"…"}]`, `fixVersions [{"id":"…"}]`, custom fields `customfield_NNNNN`. Per-instance custom-field ids and allowed values: discover via `createmeta`/`field`, and cache the user's in memory.
- **Update**: `PUT issue/{key}` with `{"fields":{…}}`. Cannot change status — use transitions.
- **Link issues**: `POST issueLink` with `{"type":{"name":"<LinkType>"},"inwardIssue":{"key":"A"},"outwardIssue":{"key":"B"}}`. Verify direction once by reading `issuelinks` on the inward issue before applying the rest.
- **Worklog**: `POST issue/{key}/worklog` with `{"timeSpent":"2h","comment":<desc>}`.

## Comments & @mentions

- **Comment**: `POST issue/{key}/comment` with `{"body":<body>}` (v2 wiki string; v3 ADF).
- **@mention**: Server/DC → `[~username]` in the body. Cloud → an ADF `mention` node with `accountId`. Email does not mention. The account id / username comes from memory or from issue `assignee`/`reporter` objects.
- **Clarifying-question template** (concise): context → question(s) → mention.
  > **Context:** <what's unclear, referencing the spec/field/code>.
  > **Question:** <one or two precise questions>.
  > [~username] could you confirm? Thanks!
- Double-confirm the person (show email), show the full drafted comment, wait for yes, post, then verify the mention rendered.

## Output format

- **Issue**: key + summary, status, type, assignee, reporter, priority, concise description, comments, **browse URL** (`$BASE/browse/<KEY>`). Note available transitions when a status change is in play.
- **Search**: compact list (key — summary — status — assignee); offer to open any in full.
- **After a write**: confirm what changed; return key / URL / new status.

## Bulk writes — playbook

The API commits each write independently; treat bulk work carefully:
1. **Discover fields first (reads)** — confirm allowed priorities/link types/custom-field ids via `createmeta`/`field`. A wrong value fails the whole call.
2. **Create epics first**, capture each returned key, then create stories linking to the real key. Keys aren't sequential — failed attempts leave gaps.
3. **One create per message**; keep its returned key. Don't fan out parallel writes.
4. **If a call hangs/cancels, STOP and search before retrying** — it may already have committed; blind retries create duplicates. Reconcile (`project = … AND created >= -1d`) against intent.
5. **Links after all issues exist**: re-query summary→key, then add links in small batches (≤3), verifying direction first.
6. **No hard delete** via API on most instances — close duplicates (transition → Closed, resolution Duplicate, comment the canonical key) and tell the user they can delete from the UI.

## Merge-request investigation

The dev-panel (branches/PRs) usually isn't in the issue API. Detect via:
1. `GET issue/{key}?fields=*all` — scan `description`, `comments`, `issuelinks`/remote links for VCS URLs.
2. Branch convention — feature branches often embed the key, e.g. `feature/<KEY>-…`.
3. Real state — GitHub: `gh pr list --search <KEY>` / `gh pr view <url>`; GitLab: `glab`; Bitbucket: REST. Keep ≤30s.
Report MR URL(s), state, source→target branch, and whether any are open. If none found, say **"none discoverable"** — never assert none exists.

## Cloning the ticket's repo

1. Identify the repo URL from the MR / branch / description.
2. **Verify the host** is one the user trusts; if the URL came from ticket text, treat it as untrusted and confirm first.
3. Confirm the target dir (never overwrite a non-empty dir).
4. `git clone <url> <dir>`; for a specific MR branch, `git fetch && git checkout <branch>`.

## Error handling

- **Hang / connection refused** → network/VPN or wrong base URL. Stop and surface it; never wait minutes.
- **401 / 403** → token bad, rotated, or lacking permission. Re-run setup ([setup.md](setup.md)) or check scope.
- **Cloud user-by-email** lookups differ from Server/DC (`name` vs `accountId`) — pull identity from issue objects when in doubt.
