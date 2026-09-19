---
type: llm
focus: trace
weight: 1
---

Grade the code review the assistant produced for the `transfer` diff.

PASS only if the review raises at least TWO of these real defects in a money-transfer function:
- No validation that `amount` is positive (a negative or zero amount reverses or no-ops the transfer).
- No check that `source` has sufficient balance (allows overdraft / negative balance).
- No atomicity / transaction — a failure between the debit and credit loses or duplicates money.
- No handling of concurrency, error/rollback, or the always-`True` return that hides failure.

Naming the underlying risk counts even if the wording differs. A severity ranking or fix suggestion is a plus but not required.

FAIL if the review raises fewer than two of these, only restates what the code does, or gives a clean bill of health.
