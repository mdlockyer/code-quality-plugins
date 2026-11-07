---
name: bug-repro
description: Turn a bug report, issue, failing scenario, or suspected defect into a fail-to-pass reproduction test with proof that it fails on the current code for the right reason and would pass on any correct fix. Use when asked to "reproduce this bug", "write a failing test for this issue", "prove this is broken", "add a regression test for the fix", when a fix is about to be written and there's no red test yet, or when a code audit has a candidate finding that needs confirming. Not for writing feature tests (use behavioral-unit-testing).
---

# Bug reproduction

A reproduction test is judged on three code states: it must **fail on the current (buggy) code**, on an assertion with a strong oracle; **pass once the bug is fixed**; and **pass on any other correct fix**, not just the one you have in mind. Agents miss the first condition about half the time (the test also passes on the bug) and the third about a quarter of the time (the test asserts the patch, not the behavior). This skill exists to hit all three every time.

## Inputs

An issue, a bug report, a reproduction scenario in prose, a stack trace, or an audit finding with a trigger and path. Plus the repository and how to run its tests. If the only input is "something's wrong with X", stop and ask for the observed behavior and the expected one before writing anything.

## Procedure

1. **Write the expectation first, from the spec.** Before reading the implementation, write down the input, the expected output or state, and *where the expectation comes from*: the issue's "expected" line, a docstring, the type signature, a caller that depends on it, the README, hand arithmetic. If the spec is silent, decide, record the assumption in the test comment, and say so in your report. Do not derive the expected value by running the code and reading the output; that is the bug's output.

2. **Choose the entry point the user would use.** The test calls the public function, endpoint, or command that the issue describes, with the issue's input, not a private helper that the fix will touch. This is what keeps the test valid for an alternative fix.

3. **Write the test** in the project's own framework and conventions, one behavior, named for it (`test_parse_amount_accepts_leading_zero`, `@Test func acceptsLeadingZero()`), with the derivation of every literal in a comment that cites the issue.

4. **Run it on the current code and keep the output.** It must fail on the assertion. If it fails with an import error, a missing symbol, a `TypeError` on `None`, or a timeout, that is not a reproduction; fix the test so the production code is actually exercised and the assertion is what fails. If it *passes*, you have not reproduced the bug: either the expectation is wrong, the input doesn't trigger it, or the bug is elsewhere. Go back to step 1; do not weaken the assertion until it fails.

5. **If you can only write a passing characterization**, write the test that pins the buggy output for the issue's scenario, confirm it passes on the current code, then invert the assertion to the spec'd value. The inverted test is the reproduction; its comment records both values and why the new one is right.

6. **Check the test is spec-aligned, not fix-aligned.** Read it once more asking: would this pass if someone fixed the bug a different way? If it asserts a helper name, a call sequence, or an error message the spec never promised, loosen it to the contract (the value, the error type, the state) while keeping it strong.

7. **Report**: the test, where its expectation came from, the exact red output on the current code, assumptions, and what the test does not cover (other manifestations of the same issue, which a fix could miss). Put the test under the project's test directory; the audit ledger gets a copy of the record.

## When a fix already exists

Revert the fix (`git stash push -- <production paths>` or `git apply -R`), run the test, confirm red on an assertion, restore, confirm green. A test that is green both ways is regression evidence, not a reproduction, and the fix has no proof yet.

## Audit use

A candidate from the `production-code-audit` skill becomes CONFIRMED when this procedure produces a red test for its trigger. The reproducer should be given the candidate's trigger, path, and impact, plus the spec source for the expected behavior, and should not be given the hunter's proposed fix.

## References

- `references/dispatch-prompts.md` — the oracle-writer procedure, for deriving the expectation independently of the implementation when the issue doesn't state it
- the `behavioral-unit-testing` skill, when installed — the four questions, §9 of its oracle ladder (fail-to-pass tests and the three code states, with rewrites), and the domain playbook
