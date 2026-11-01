# ste — deep dive

> On-demand companion to `lore/ste.md`. **Do not read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Avoid and use word list](#word-list) · [Word counting](#word-counting) · [Rewrite patterns](#rewrite-patterns)

## Avoid and use word list <a id="word-list"></a>

This is magician's own short list. It is STE-inspired, not the STE dictionary, and it makes no compliance claim. Technical nouns and technical verbs are exempt. Examples: `execute` a command, `validate` a schema, `implement` an interface. The term stays as the code names it.

| Avoid | Use |
|---|---|
| accomplish, achieve | do, complete |
| additional, further | more |
| adjacent, close (adjective) | near, next to |
| assist | help |
| attempt (verb) | try |
| commence, initiate, begin | start |
| component (generic) | part |
| demonstrate | show |
| e.g., i.e., etc., vs. | for example, that is, and so on, against |
| ensure, guarantee | make sure |
| facilitate | make easier, help |
| frequently | often |
| functionality | function |
| furnish, provide (supply sense) | give, supply |
| however, nevertheless | but |
| immediately | at once, now |
| implement (general) | do, install, add, or the specific technical verb |
| in order to | to |
| in the event that, in case | if |
| indicate | show |
| locate (find sense) | find |
| may (possibility, non-normative text) | can |
| modify, alter | change |
| multiple, numerous, various | many, several, more than one |
| obtain, acquire | get |
| optimal | best |
| perform, carry out, execute (generic) | do, or the specific verb |
| permit, allow, enable (general sense) | let, can |
| prior to, previous to | before |
| regarding, concerning, with respect to | about |
| require, necessitate | need, must |
| retain | keep |
| set up (phrasal, software sense) | install, configure |
| shall, should (requirement, non-normative text) | must |
| subsequent to, following (as a preposition) | after |
| sufficient, adequate | enough |
| terminate, conclude | stop, end |
| therefore, consequently, hence | so, thus |
| utilize, employ | use |
| verify, validate, confirm (check sense) | check, make sure |
| via, by means of | with, through |

When a source text uses `MUST`, `SHOULD` or `MAY` as normative words (RFC 2119), keep them. The rows for `shall`, `should` and `may` apply to your own prose only.

## Word counting <a id="word-counting"></a>

Count words the STE way before you apply the 25-word and 20-word limits:

- A number with its unit is one word (`30 s`, `2 GB`).
- A hyphenated group is one word (`read-only`, `test-driven`).
- An identifier, a path, a URL, a flag and a quoted string are one word each.
- An abbreviation and an ID are one word each (`PR 42`, `HTTP`).
- A proper noun is one word (`Claude Code`, `GitHub Actions`).
- Text in parentheses counts as one word of the host sentence. Count it again on its own, under the same limit.
- A colon that opens a vertical list ends the sentence. Each list item is its own sentence.

## Rewrite patterns <a id="rewrite-patterns"></a>

Each pair shows a sentence that breaks a rule, then one that keeps it.

- Gerund head: "Running the tests shows the failure." Use: "Run the tests to see the failure."
- Perfect tense: "The build has failed twice." Use: "The build failed twice."
- Progressive tense: "The server is listening on port 8080." Use: "The server listens on port 8080."
- Passive step: "The cache should be cleared before the deploy." Use: "Clear the cache before the deploy."
- Command before condition: "Restart the service if the config changed." Use: "If the config changed, restart the service."
- Two instructions: "Open the file and then change the port." Use: "Open the file. Change the port."
- Semicolon: "Run the migration; then start the app." Use: "Run the migration. Then start the app."
- Contraction: "The test doesn't pass." Use: "The test does not pass."
- Latin abbreviation: "Use a linter, e.g. ruff." Use: "Use a linter, for example ruff."
- Noun cluster: "the plugin session start hook budget" Use: "the budget of the session start hook".
- Nominalisation: "Perform the installation of the package." Use: "Install the package."
- Hidden action in a note: "NOTE: the key must be rotated." Use: "CAUTION: Rotate the key before the deploy. An old key fails authentication."
- Inline list of three or more: "Set the host, the port and the timeout." Use a vertical list with one item per line.
- Over-shortened: "Error. Retry." Keep the facts: "The request returned `503 Service Unavailable`. Retry after 30 s."
