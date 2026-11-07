---
trigger: glob
globs: "**/test_*.py, **/*_test.py, **/tests/**, **/__tests__/**, **/*.test.*, **/*.spec.*, **/*Tests.swift, **/*Test.swift, **/*_test.rs, **/tests.rs"
description: Four questions for any test you write or change; the behavioral-unit-testing skill has the full version.
---

A test exists to fail when the code is wrong. Before you finish a test, answer these:

1. **Where did the expected value come from?** The spec, the issue, a docstring, hand arithmetic, a caller — not from running the code and copying its output. If you've already read the implementation, derive the expectation from the spec anyway and weight question 2 more.
2. **How do you know it fails on wrong code?** Think of three states: the code before your change, with it, and some other correct implementation. The test must fail on the first (on an assertion, not an import error), pass on the second, and pass on the third. When a test passes, ask: *would this have passed before my change?* If yes, it is not evidence about the bug or feature. Prove it with a revert, a deliberate mutant, or the red output on the old code.
3. **Did you change a test to make something pass?** Skipping, `.only`, loosening a tolerance, swapping a value for a wildcard, updating the expected to the actual, special-casing the inputs, catching the assertion. A red test means the code is wrong until you can say why not; say the reason before touching the test.
4. **Did you satisfy the check, or do the job?** Run the real entry point the way a user would. The test must exercise the artifact that was asked for, not a demo or a copy of its logic. Say what the checks don't cover.

Assert exact values, specific errors, resulting state, or spec-derived properties. Non-null, truthy, didn't-throw, mock-was-called, and unreviewed snapshots pass against `return nil`. One behavior per test, named for it; literals carry their derivation in a comment; no conditionals in a test body; inject the clock and the seed; sort or compare as sets where order is unspecified; never patch the unit under test.
