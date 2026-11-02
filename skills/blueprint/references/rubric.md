# Plan rubric

Grade the plan against each claim before the Completion Signal. Mark each claim met or unmet. List every unmet claim, with the fix, at the gate in step 7. `plan-render check` already enforces the schema. These claims check what the schema cannot.

1. Every requirement in the spec maps to at least one step. Name any requirement with no step.
2. Every step has a `red.test` with a test file and a test name. Its `red.run` command fails before the change.
3. Every step has a `verify` list of exact commands that exit 0 on success. None of them is a phrase such as "run the tests".
4. `constraints` matches the spec's constraints word for word.
5. No two `parallel: true` steps in one wave change or read the same file.
6. Every step has an effort between 5 and 60 minutes.
7. Every step that touches a shared interface, shared data or a migration has `risk.level` `medium` or `high`.
8. Every `depends_on` entry names an earlier step.
9. `context.blast` is present only when `kg blast` produced it. No row is estimated.
10. The last wave ends with a verification step that runs the project's full check (`/certify` or its commands).
