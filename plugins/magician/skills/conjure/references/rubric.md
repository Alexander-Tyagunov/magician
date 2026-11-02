# Spec rubric

Grade the spec against each claim before the Completion Signal. Mark each claim met or unmet. List every unmet claim, with the fix, in the GATE 4 message. Each claim is a check you can run on the file, not a matter of taste.

1. The spec has exactly one **Goal** line, and it is one sentence.
2. Every requirement is a single bullet that a test or a manual check can prove. No bullet uses "should be fast", "user-friendly" or "robust" without a number or an observable result.
3. Every requirement maps to at least one entry in **Components** or **Testing Strategy**.
4. Every path in **Components** either exists in the repository or is marked new, with one responsibility per path.
5. **Error Handling** names at least one failure case per external call or user input in the requirements.
6. The **Testing Strategy** section names the test command or framework the project already uses.
7. The spec names the approach chosen at GATE 1, and a decision record for it exists under `.workspace/shared/decisions/`.
8. In a visual mode, **Design Artifacts** names the mode, the screens folder and the approved file, and that file exists.
9. The spec has no `TBD`, `TODO` or `?` placeholder.
10. When `.workspace/shared/north-star.md` exists, the spec has one `**North star:**` line: `fits`, or `conflicts because <reason>`.
