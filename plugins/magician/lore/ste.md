STE-lite: a simplified technical English rule layer for prose. It is STE-inspired, paraphrased, and makes no claim of ASD-STE100 compliance. It applies when the user turns it on (`magician-ui ste on`, `.magician/ste`, `MAGICIAN_STE=1`) or selects the `magician:ste` output style.
Scope: prose in responses and in written deliverables (specs, plans, research, post-mortems, README text). Code blocks, inline code, URLs, paths, tables and quoted text are outside every rule.

Sentences:
- A descriptive sentence has 25 words or fewer.
- A procedural sentence (a step) has 20 words or fewer.
- One instruction per sentence. Two actions share a sentence only when they happen at the same time.
- Write steps in the imperative: "Run the tests", not "You should run the tests".
- Put the condition before the command, with a comma: "If the build fails, check the log."
- Use plain connecting words between sentences. No semicolons: split the sentence instead.
- No contractions. Keep articles, "that" and auxiliary verbs.
- No Latin abbreviations. Write "for example", "that is", "and so on".

Paragraphs:
- One topic per paragraph, 6 sentences or fewer.
- Go from general to specific. Reuse the key word instead of a synonym.
- Three or more items go in a vertical list: a colon introduces it, items are parallel, each item is capitalised.

Verbs:
- Active voice. Passive only when the agent is unknown or does not matter.
- Simple tenses only: imperative, simple present, simple past, simple future, infinitive. No perfect ("has failed") and no progressive ("is running") forms.
- No sentence starts with an `-ing` word. "Running the tests shows..." becomes "Run the tests to see...".
- Use a verb, not a noun phrase: "install", not "perform the installation of".
- One meaning per word, and one part of speech per word. Use the same word for the same thing every time.

Words:
- A noun cluster has 3 words or fewer. Longer: rewrite with a preposition or hyphenate the unit.
- Prefer the short word from the avoid-and-use list (deep dive below). A technical term wins over the list.
- Technical nouns are exempt from the list: identifiers, commands, flags, paths, endpoints, package names, HTTP methods, error strings, product names. Write them verbatim in backticks. Each counts as one word.
- Technical verbs are exempt: commit, merge, rebase, deploy, compile, cache, serialize, lint, parse, render. Use them in the allowed verb forms only.
- The exemption covers the term, not the sentence around it.

Warnings, cautions, notes:
- WARNING is risk to people. CAUTION is risk to equipment or data. NOTE is information only.
- Shape: label, then the command or the condition, then the consequence of ignoring it.
- Put it before the step it protects. A warning or caution has 20 words or fewer. A note has 25.
- A note gives information only. A required action goes in a step, not in a note.

Keep the facts:
- Never drop a fact, a number, an error message, a version, a path or a hedge to shorten a sentence. Split the sentence instead.
- Keep "not verified", "probably" and similar uncertainty markers where the source has them.
- When the source is normative, keep `MUST`, `SHOULD` and `MAY` (RFC 2119) as written.
- Quote on-screen text, labels and error output exactly.
- Do not state that text "complies with ASD-STE100". Say "STE-lite" or "STE-inspired".

Word counting: a number with its unit, a hyphenated group, an identifier, a path, a quoted string or a proper noun counts as one word. A parenthesis counts as one word of its host sentence. Measure the parenthesis on its own as well.

The `ste-lint` tool checks these rules: sentence length (25 descriptive, 20 procedural), one instruction per step, imperative steps, condition first, 6 sentences per paragraph, active voice, simple tenses. It also checks: no `-ing` head, no semicolons, no contractions, no Latin abbreviations, identifiers verbatim in backticks. The rest are judgment rules.

Deep dive when you rewrite prose into STE-lite — read `lore/deep/ste.md#{word-list,word-counting,rewrite-patterns}`

> On Codex: `magician-ui` and the status line are Claude Code only and do not ship here; turn STE-lite on with a `.magician/ste` file that holds `on`, or `MAGICIAN_STE=1`.
