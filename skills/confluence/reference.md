# Confluence REST reference (direct HTTP)

Loaded on demand from [SKILL.md](SKILL.md). All calls are `curl` to the Confluence REST API — no MCP.

## Auth & the CLI

The bundled **`confluence` CLI** handles auth and the base URL from the environment — **do not build `curl` by hand**. It reads `CONFLUENCE_BASE_URL` (Cloud includes `/wiki`; Server/DC may include a context path), a token (`CONFLUENCE_API_TOKEN` / `CONFLUENCE_PAT` / `CONFLUENCE_PROD_PAT`), and `CONFLUENCE_EMAIL` (set → Cloud Basic; else Server/DC Bearer). Verify with `confluence whoami`; `401` = bad/rotated token.

The REST paths below are what **`confluence raw <METHOD> <path> [json-body]`** expects — the path is appended to `<base>/rest/api/`. Use the named commands (`get`, `search`, `whoami`) for common reads; use `confluence raw` for children/comments/labels and all writes.

## Page ids & URLs

- `page_id` is the reliable key — extract from the URL: `…/pages/<id>/…` or `…/viewpage.action?pageId=<id>`.
- Human URL to present: `$BASE/spaces/<SPACE>/pages/<id>` (or `…/viewpage.action?pageId=<id>` when the space key is unknown).

## Reads & CQL

- **Whole page**: `confluence get <id> body` returns the **entire** page as block-aware readable text (headings, list items, and table cells preserved; entities decoded) — no cap. `confluence get <id> storage` returns the exact `body.storage` XHTML for editing or macro inspection. Under the hood this is `GET content/{id}?expand=space,version,body.storage` (add `,body.view` for rendered HTML).
- **Large page**: you no longer have to work around a size cap — `body` is complete. To trim output deliberately, set `CONFLUENCE_BODY_MAX=<chars>` (0/unset = full) or extract the heading you need from `storage`. (`CONFLUENCE_RAW_MAX` similarly caps `confluence raw`; default full.)
- **Children / tree**: `GET content/{id}/child/page?limit=50`.
- **Comments**: `confluence comments <id>` lists every comment with full block-aware bodies (paginated). Raw form: `GET content/{id}/child/comment?expand=body.storage,version`. **Labels**: `GET content/{id}/label`.
- **Search (CQL)**: `GET content/search?cql=<urlencoded>&limit=25&expand=space` (URL-encode with `-G --data-urlencode`). Always pass a `limit` (≤50). Examples:
  - In a space — `space = <KEY> AND text ~ "<term>" ORDER BY lastmodified DESC`
  - By title — `title ~ "<name>"`
  - Recent — `space = <KEY> AND lastmodified >= now("-30d")`
  - By label — `label = "<label>"`
- **Inspect macros**: read `body.storage` (XHTML) and look for `ac:structured-macro ac:name="…"` — the storage reveals macros the rendered/markdown view hides.

## Writes

1. Resolve the target `page_id` (updates) or `space` key (creates). **Search first** — titles are unique per space; update if found, else create.
2. Show the user the full proposed content (a diff for edits) and get a yes.
3. **Create**: `POST content`
   ```json
   {"type":"page","title":"…","space":{"key":"<KEY>"},
    "ancestors":[{"id":"<parentId>"}],
    "body":{"storage":{"value":"<p>…</p>","representation":"storage"}}}
   ```
4. **Update**: first `GET content/{id}?expand=version` to read the current version number, then `PUT content/{id}`
   ```json
   {"version":{"number":<current+1>,"message":"<edit summary>"},
    "type":"page","title":"…",
    "body":{"storage":{"value":"<full new XHTML>","representation":"storage"}}}
   ```
   `update` replaces the **entire** body — pass the full intended content. (Use `representation:"wiki"` to send wiki markup instead of XHTML — see [authoring.md](authoring.md).)
5. **Comment**: `POST content` with `{"type":"comment","container":{"id":"<pageId>","type":"page"},"body":{"storage":{"value":"<p>…</p>","representation":"storage"}}}`.
6. **Label**: `POST content/{id}/label` with `[{"prefix":"global","name":"<label>"}]`.
7. Report the page title + URL after.

## Output format

- **Page**: title, space, a concise summary (or the requested section), the **human URL**. Summaries must be substantially shorter than and different from the source.
- **Search**: compact list (title — space — snippet — URL); offer to open any in full.
- **After a write**: confirm what changed; return title + URL.

## Error handling

- **Hang / connection refused** → network/VPN or wrong base URL. Surface it; never wait minutes.
- **401 / 403** → token wrong/rotated or insufficient permission. Re-run setup ([setup.md](setup.md)).
- **409 on update** → stale version; re-`GET` the version number and retry once.
- **User-by-email** lookups differ Cloud (`accountId`) vs Server/DC — pull identity from page authors when unsure.
