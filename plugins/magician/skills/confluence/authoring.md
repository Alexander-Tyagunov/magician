# Confluence authoring — formats & macros

Loaded on demand from [SKILL.md](SKILL.md). How to write content the create/update calls accept, the macros you can embed, and validation rules.

## Body representations

The REST body takes a `representation`:

| Representation | When to use |
|---|---|
| `storage` *(recommended for writes)* | Confluence storage (XHTML). Full control; required for macros, columns, layouts. |
| `wiki` | Confluence wiki markup — concise macro syntax `{macro:params}`. Easier than XHTML for simple macros. |

Markdown is **not** a native REST representation. Convert Markdown → `storage` XHTML (paragraphs `<p>`, headings `<h2>`, lists `<ul><li>`, code `<ac:structured-macro ac:name="code">`), or send wiki markup with `representation:"wiki"`. **Pick the lowest-power form that works**: plain XHTML for ordinary prose; wiki/storage macros only when needed.

## Wiki markup quick reference (`representation:"wiki"`)
- Headings `h1.`…`h6.`; `*bold*`; `_italic_`; monospace `{{text}}`
- Code `{code:java}…{code}`; unformatted `{noformat}…{noformat}`
- Tables: header `||A||B||` then `|a|b|`
- Macros: `{info}`, `{note}`, `{warning}`, `{tip}`, `{panel:title=…}`, `{expand:title=…}`, `{toc}`, `{status:colour=Green|title=DONE}`, `{children}`

## Storage (XHTML) basics (`representation:"storage"`)
Macros take the form:
```xml
<ac:structured-macro ac:name="NAME">
  <ac:parameter ac:name="key">value</ac:parameter>
  <ac:rich-text-body><p>body</p></ac:rich-text-body>
</ac:structured-macro>
```
Info callout:
```xml
<ac:structured-macro ac:name="info"><ac:rich-text-body><p>Heads up.</p></ac:rich-text-body></ac:structured-macro>
```
Code block:
```xml
<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">java</ac:parameter><ac:plain-text-body><![CDATA[ ... ]]></ac:plain-text-body></ac:structured-macro>
```

## Common macros
info / note / warning / tip (callouts) · code · toc · expand (collapsible) · panel · status (lozenge) · children · jira (embed issues). Availability depends on the plugins installed on **this** instance — treat the list as a baseline, not a guarantee. To copy an exact macro, read an existing page's `body.storage` and mirror it.

## Validations & gotchas

- **Title is unique per space** — create fails if it exists; search first, update if found.
- **Version** — `update` must send `version.number` = current + 1; add a `version.message`. A `409` means the version was stale; re-read and retry once.
- **Hierarchy** — set `ancestors:[{"id":"<parentId>"}]` to nest a page.
- **Don't clobber** — `update` replaces the whole body; pass the full intended content.
- **Labels** are set via the label endpoint, not page content.
- **Reading macros** — the rendered/markdown view hides some macros; inspect `body.storage` to see the real XHTML.
