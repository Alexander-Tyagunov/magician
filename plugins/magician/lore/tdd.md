Common AI mistakes: writing implementation before the failing test; writing multiple failing tests before making any pass; testing implementation details instead of behavior; skipping refactor phase after green.
Pattern: Red -> Green -> Refactor. One behavior at a time. Test public interface, not internals. Use test doubles at system boundaries only.
Gotchas: a test that never fails is not a test; test names should describe the behavior being verified; table-driven tests reduce duplication.
