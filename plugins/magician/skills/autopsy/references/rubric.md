# Post-mortem rubric

Grade the post-mortem against each claim before the Phase 6 commit gate. Mark each claim met or unmet. List every unmet claim, with the fix, in the draft you show at Phase 6.

1. The header has a date, a severity (P1, P2 or P3), a duration and an impact with a number (users, requests, minutes or money).
2. Every timeline entry has a time and a source (git log, CI, monitoring or manual).
3. The timeline has a start, a detection, a mitigation and an end entry.
4. The 5 Whys chain ends at a process or system cause, not at a person.
5. No sentence names a person as the cause. Owners are roles.
6. Every root cause has at least one action item, and every action item names the Why it prevents.
7. Every action item has an owner role, a deadline date and a status.
8. At least one action item is in Detection or Prevention.
9. The eval skeleton from Phase 5b exists, or the draft says why the incident has no testable trigger.
