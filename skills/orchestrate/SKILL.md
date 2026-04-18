---
name: orchestrate
description: Drives full multi-agent implementation from a blueprint — parallel where safe, sequential where required
keep-coding-instructions: true
---

# /orchestrate — Multi-Agent Implementation

Execute an entire blueprint using parallel and sequential agent dispatch.

## Inputs Required

If the plan file is not clear from context, ask: "Which blueprint plan should I execute? (I'll use the most recent file in `.workspace/shared/plans/` if you don't specify.)"

**End your turn. Wait for their reply (or proceed with most recent if context is unambiguous).**

## Process

1. **Read the blueprint** — extract all tasks with their parallelism annotations
2. **Build execution graph** — group parallel tasks into waves, sequential tasks as singletons
3. **Execute wave by wave**:
   - For each wave: use /summon to dispatch all parallel tasks simultaneously
   - Wait for all tasks in the wave to complete before starting the next
   - For sequential tasks: dispatch one agent, wait for completion
4. **After each wave**: run a quick sanity check (`git status`, `git log --oneline -3`)
5. **After all waves complete**: run /certify
6. **Report** — show completed tasks, any blockers encountered

## Execution Graph Example

```
Wave 1 (parallel): Task 1, Task 2, Task 3
Wave 2 (sequential): Task 4 (depends on 1, 2, 3)
Wave 3 (parallel): Task 5, Task 6
Wave 4 (sequential): Task 7 (integration, depends on all)
```

## Conflict Detection

After each wave, check for merge conflicts:
```bash
git status | grep -i conflict
```
If conflicts found: pause and resolve before continuing.

## Completion Signal

"Orchestrate complete. N tasks executed across M waves. Run /scrutinize for code review."
