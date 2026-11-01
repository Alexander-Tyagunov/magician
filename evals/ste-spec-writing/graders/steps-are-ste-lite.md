---
type: llm
weight: 2
---

Grade the spec in the assistant's final message against magician's STE-lite rules for steps.

PASS only if ALL of these hold for the numbered list of six steps:
- Every step is exactly one sentence, written in the imperative form ("Add ...", "Return ...", not "You should add ..." or "The tool adds ...").
- Every step has at most 20 words. Count an inline code span (backticked text), a path, a number with its unit and a hyphenated group as one word each.
- No step uses a perfect tense ("has copied", "have added") or a progressive form ("is copying", "are running").
- Every identifier, command, flag or path (such as the flag name, the tool name, the folder names) is written in backticks.
- There are exactly six steps.

FAIL if any step breaks one of these rules, if the list has more or fewer than six steps, or if the message is not a spec (a question back, a refusal, or file edits instead of chat text).
