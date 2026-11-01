---
name: ste-spec-writing
description: With STE-lite on, a short spec Claude writes keeps to the checkable rules — imperative steps of at most 20 words, no semicolons, no contractions, no Latin abbreviations, no perfect or progressive tenses, identifiers in backticks. The deterministic graders mirror tools/ste-lint's W2, W3 and W6; the rubric covers S2 and V2. Self-contained for the eval sandbox.
tags: [regression, prose, ste]
runs: 3
max_turns: 4
expected_outcome: The final message is a six-step spec in STE-lite prose, every step one imperative sentence of at most 20 words, with no semicolon, contraction or Latin abbreviation anywhere in it.
allowed_tools: [Read, Grep, Glob]
---

STE-lite is on for this project (the `.magician/ste` setting is `on`): write prose in magician's simplified technical English. The rules that matter here: one instruction per sentence, imperative form for steps, a step has at most 20 words, a descriptive sentence at most 25, no semicolons, no contractions, no Latin abbreviations such as e.g. or i.e., only simple tenses (no "has finished", no "is running"), the condition before the command, and every identifier, command, flag and path in backticks.

Write a short spec, as your final message and nothing else, for adding a `--dry-run` flag to a command-line tool named `syncer` that copies files from a `source` folder to a `target` folder. The spec has two parts:

1. A one-paragraph summary (at most four sentences).
2. A numbered list of exactly six implementation steps.

Do not create or edit any file; answer in the chat.
