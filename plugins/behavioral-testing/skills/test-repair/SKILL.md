---
name: test-repair
description: Repair tests that a test audit found weak, flaky, pinned to one implementation, or suspicious, with proof for every change: a surviving mutant that now dies, a revert that now goes red, or a shuffled run that now agrees. Use after a test audit when the user approves findings, or when asked to "fix these tests", "strengthen the assertions", "make this test actually test something", "un-mock this", or "fix the flaky tests". Never silently changes what a test asserts; tests that enforce suspicious behavior are escalated, not rewritten.
---

# Test repair

Repair is where agents do the most damage to a suite, because "fix the test" is one keystroke from "update the expected value to the actual one". Every repair here is one of three named moves, each with its own proof, and the proof is produced by a different agent than the one that wrote the change.

Input: the test-audit ledger (`../<repo>-test-audit/`) and the list of findings the user approved. Repair nothing that wasn't approved. If no audit exists, run `test-audit` first, or in Quick mode on the files named.

## The three moves

**Strengthen** (lens 1, can't fail). Rewrite the assertion up the oracle ladder: exact value, specific error, resulting state, or a property. Expected values come from an `oracle-writer`, which is given the spec, interface, docstring, and callers of the unit, and not its implementation, because tests written with the implementation visible measurably assert what it does rather than what it should. Each literal carries its derivation in a comment. Proof: the mutant recorded in the finding now kills the test, with output.

**Untangle** (lens 4 pinned; over-mocked; lens 5 brittle). Replace interaction assertions with state assertions; replace a mock of the unit's collaborator with the real one or a fake with real behavior; inject the clock, seed, or scheduler; sort or compare as sets where order is unspecified; isolate shared state. Proof: the test passes on the current code *and* on a deliberately different correct implementation of the same contract (the `test-prover` writes a second implementation or a semantics-preserving refactor of the unit, runs the test against it, reverts), and for brittleness, N shuffled runs agree.

**Escalate** (lens 3, suspicious behavior; lens 2, regression-only). Do not rewrite. Produce a decision for the human: "test X asserts Y; spec/docstring/callers imply W; which is right?" If the user says the behavior is the bug, invert the test into a fail-to-pass reproduction (the `bug-repro` skill) and hand the code finding to the production audit or the user. If the user says the test is right, update the spec or docstring so the next audit doesn't flag it, and close the finding. If the regression-only test was the sole evidence for a shipped fix, write the missing fail-to-pass test with `bug-repro`.

## Procedure

Done when every approved finding has a repair record with proof, or an escalation record with the two candidate truths.

1. Group approved findings by production unit so one `oracle-writer` can derive all the expected values for a unit at once, from the spec and callers.
2. For each finding, dispatch a `test-repairer` with the finding file, the oracle-writer's expected values, the oracle ladder, and the project's testing conventions. The repairer edits only the named test(s), keeps the test name and behavior-per-test discipline, and writes a repair record: before/after, the derivation of each literal, assumptions made.
3. Dispatch a `test-prover` to produce the proof for the move (mutant now dies; alternative implementation passes; shuffled runs agree). The prover restores any mutant or alternative implementation and checks the working tree.
4. Dispatch a fresh-context `test-verifier` per repaired test. It checks: the repaired test fails on the mutant and on the pre-fix state where one exists; it passes on the current code; it would pass on a different correct implementation; the expected values trace to a spec, docstring, or caller, not to the code's output; and the repair changed nothing except the named test. A verifier rejection sends the finding back with the reason.
5. Run the full suite after each unit's repairs, with real output. A repaired test that breaks another test has found something; stop and report rather than adjust.
6. Report in the conversation: tests changed and why, the proof per test, assumptions, escalations awaiting a decision, and anything the suite's own run revealed.

## Rules

- **Expected values never come from running the code.** If the oracle-writer cannot derive a value from spec, docstring, callers, or hand arithmetic, the test becomes a labeled characterization test (`test_characterize_*` plus a comment) and the surprising output is reported, not enshrined.
- **One finding, one diff.** Reviewable changes; no drive-by rewrites of neighboring tests.
- **No deletions without a replacement or a decision.** A redundant weak test may be deleted only when the verifier confirms a stronger test covers the same path and the user approved deletion.
- **Convergence.** Diff-only re-review after the first round, no repeat findings, and after a third round on the same test, stop and report that the unit's contract is unclear rather than iterating.
- **Nothing inside the repository except the test edits themselves.** Records, proofs, and alternative implementations live in the ledger.

## References

- `../behavioral-unit-testing/SKILL.md` — the four questions every repaired test must answer
- `../behavioral-unit-testing/references/oracle-ladder.md` — weak → strong rewrites per language
- `../behavioral-unit-testing/references/domain-playbook.md` — async, time, databases, HTTP, UI, LLM features
- `../test-audit/references/lenses.md` — what each lens finding means and the severity rubric
