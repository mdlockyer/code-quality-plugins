---
name: test-audit
description: Audit a test suite for tests that cannot fail, tests that pass on the bug, tests that enforce wrong behavior, tests pinned to one implementation, and flaky tests; prove each finding with a surviving mutant; report with coverage and stop for approval. Use when asked to audit, review, grade, or assess tests or a test suite, when someone says "are these tests any good", "do our tests actually catch bugs", "why did this ship with green tests", "check our test quality", or before trusting a suite as an oracle for other work. Not for writing new tests (use behavioral-unit-testing) or fixing them (use test-repair).
---

# Test audit

The question is not "how much is covered" but "which tests would go red if the code were wrong". Most agent-written tests never would: in an 86k-patch field study, 80% of agent test patches had weak or no oracle, and nearly half of the passing checks agents collect also pass on the buggy code. A suite like that is not an oracle for anything, including this audit's own reproduction tests, so audit the suite before you trust it.

This is a search, not a read. Enumerate every test, rank by weakness and stakes, examine each file narrowly, **prove** each finding by breaking the code and watching the test stay green, and let a fresh-context verifier throw out what doesn't hold up.

## Workers

Three roles do the narrow work, each with a procedure in `references/dispatch-prompts.md` whose first paragraph lists the slots its task message needs: the **auditor** (one test file, five lenses, read-only), the **prover** (breaks the production code deliberately, runs the test, records the output, restores), and the **verifier** (fresh context; re-runs the proof and tries to reject). If your harness has named agents for these roles (a plugin build ships them as `test-auditor`, `test-prover`, `test-verifier`), dispatch those and send only the slots. Otherwise send the procedure plus the slots to a fresh-context worker. With no subagents at all, perform each role yourself, one file at a time, writing each result to the ledger before the next, and re-read finding files cold from disk before verifying them.

## Ledger

Outside the repository (default `../<repo>-test-audit/`), never committed:

```
inventory.md / inventory.json   every test file: tier counts, mock density, smells, stakes rank, status
oracles.md                      suite run, shuffled run, mutation run, coverage: commands and real output
findings/<test-file-id>.md      per-file hunt results, one section per lens
candidates.md                   one line per candidate with status
report.md                       the deliverable
```

Statuses: `SPECULATIVE` (looks weak), `CONFIRMED` (a deliberate mutant or revert left it green, with the output), `REJECTED` (verifier found it does catch something, or the mutant is equivalent). Only CONFIRMED reaches the main report.

## Where things run

Same rule as the production audit: read files wherever they are, run the suite and mutation tools wherever the toolchain is, move text not trees, never archive or transfer the repository. Work out the topology before phase 0 and write it at the top of `oracles.md`.

## Phase 0 — Inventory and oracles

Done when every test file has a row in `inventory.md` with a stakes rank, and `oracles.md` records a suite run.

1. Run `python <skill-dir>/scripts/test_inventory.py <repo> --out <ledger>/inventory.json` where it can reach the repo (it also writes `inventory.md`). It classifies each test by oracle tier (W1 no assertion, W2 existence, W3 boolean, W4 interaction-only, W5 snapshot-only; S1 value, S2 error/state, S3 multi-signal), counts mocks, conditionals in test bodies, skip markers, sleeps, and unsorted comparisons, and maps each test file to the production units it names. Swift (XCTest, Swift Testing), TypeScript/JavaScript (Jest, Vitest, Mocha, node:test), Rust (`#[test]`, proptest), and Python (pytest, unittest) are classified well; other languages get a coarse pass. It is a heuristic; the stakes rank is yours to set.
2. **Rank by weakness × stakes.** A file of W2 tests guarding billing or auth outranks a file of W2 tests guarding a logger. Use what the tests cover (their imports and names), the production audit's inventory if one exists, and git history (`git log --stat` for the units with the most fix commits).
3. **Run the suite** and record the command and output. Then **run it again shuffled** (`pytest -p randomly`, `vitest --sequence.shuffle`, `cargo test -- --shuffle`, `swift test` with `--parallel`, or two plain runs if no shuffle exists). Any test whose result changes is a CONFIRMED flaky finding already.
4. **Run a mutation tool if one is present or a one-line install** (`cargo-mutants`, Stryker, `mutmut`, `muter` for Swift), incrementally, on the top-ranked units only, not the whole repo. Record survivors per unit. In Quick mode skip this; in Deep mode widen it.
5. Note what the project considers its testing conventions (test helpers, fixtures, a `testing.md`), so findings don't flag the convention itself.

## Phase 1 — Hunt

Done when every rank-4/5 test file (Deep: rank 3 too) has a findings file with a result for each lens.

Dispatch one auditor per test file. The auditor runs the five lenses in `references/lenses.md` as separate passes and answers each with candidates or `nothing applies: <reason>`:

1. **Can't fail** — no assertion, existence-only, boolean-only, interaction-only, unreviewed snapshot, patched unit under test, expected value computed from the code's own formula or helper.
2. **Would pass on the bug** — for tests that accompany a fix (find them via `git log -- <test file>` and the linked commit), the test must fail with the production change reverted; one that doesn't is regression-only evidence that was mistaken for a reproduction.
3. **Enforces suspicious behavior** — expected values that contradict the spec, docstring, or naming; characterization tests presented as specification; a test that locks in an off-by-one, a wrong rounding, a swallowed error.
4. **Pinned to one implementation** — asserts a call sequence, a private helper, a mock interaction, or a patch-specific detail that a different correct implementation would violate.
5. **Brittle or flaky** — fixed sleeps, real clocks, real randomness without a seed, unsorted collection comparisons, shared mutable state, order dependence, network.

Every candidate names `file:test_name`, the lens, the specific line, what the test would need to assert instead, and (for lens 1 and 3) the production unit it covers. A candidate without a line is a hunch and stays SPECULATIVE.

Hunters also look for **variants**: once a weak pattern is found (a helper that returns `True` for everything, a fixture that mocks the repository), grep the suite for every other use and report the class once with all locations.

## Phase 2 — Prove

Done when every lens-1 and lens-3 candidate has either a mutant record or a reason execution wasn't possible.

Dispatch a prover per unit (batching the candidates that cover it). The prover breaks the production code the test is supposed to guard — flip a comparison, move a boundary by one, delete a branch, return a constant, drop an error path — runs the candidate test, and records the exact mutation and output. Test still green → CONFIRMED, and the mutant goes in the finding file (it becomes the acceptance test for the repair). Test goes red → the candidate is rejected with the mutant that killed it; the prover then checks whether the kill came from the strong assertion or from a crash (a `TypeError` on `None` is not a kill). The prover always restores the code and verifies the working tree is clean before returning.

Where a mutation tool ran in phase 0, its survivors on the unit are prior evidence; the prover still writes the one hand-picked mutant, because tool mutants are often equivalent or trivial and a human needs one they can read.

## Phase 3 — Verify

Done when every CONFIRMED candidate has a verdict.

Dispatch a fresh-context verifier per finding (or small batch). It re-reads the cited lines, tries to reject: is there *another* test in the suite that catches the mutant (then the finding is "redundant test", a Low, not "unguarded unit")? Is the mutant equivalent (behavior unchanged)? Is the "suspicious" expected value actually what the spec says? Is the "pinned" assertion a documented contract? It re-rates severity with the rubric in `references/lenses.md` and dedupes to one finding per root cause.

## Phase 4 — Report and stop

Write `report.md` in the format in `references/report-format.md`: counts first, then audit coverage (files examined, lenses run, oracles run with real output, mutation survivors by unit, what was skipped), then findings by severity, each with `file:test_name`, the lens, the surviving mutant and its output, the production unit left unguarded, and the proposed repair move (strengthen, untangle, or escalate). Lens-3 findings are flagged for a human decision: the test may be wrong, or the code may be — the audit doesn't decide.

**Stop and ask which findings to repair.** The audit never edits tests or code. Repairs go through `test-repair`.

## Modes

| Mode | When | What changes |
|---|---|---|
| Quick | A small package, or "just tell me if these tests are any good" | Inventory + shuffled run; hunt lenses 1 and 5 on rank-5 files; prove by hand-mutant only |
| Standard (default) | A service, app, or library | Everything above, mutation tool on top-ranked units |
| Deep | Before trusting the suite as an oracle (a production audit, a big refactor, a launch) | All lenses on rank-3+ files, mutation tool across every unit with fix history, two independent auditors on rank-5 files |

## How this audit goes wrong

- **Counting instead of proving.** A grep for `assert is not None` is an inventory, not a finding. The mutant is the finding.
- **Flagging the convention.** A project that asserts through a shared `assertValidOrder` helper is not "assertion-free". Read the helper; flag it only if *it* can't fail.
- **Treating coverage as an oracle.** Lines executed with nothing checked is the thing this audit exists to expose. Report checked coverage if you can measure it, never line coverage as evidence of quality.
- **Repairing during the audit.** The temptation is strongest on lens 3: don't "fix" a test that enforces a bug, because the code may be the thing that's wrong. Escalate.
- **Leaving a mutant in.** The prover restores and checks `git status` every time. The verifier checks it again.

## Guardrails

- No edits to tests or code during the audit; mutants live only for the duration of one run and are always reverted.
- No invented numbers: mutation scores, survivor counts, and flaky rates come from recorded runs.
- Severity from the rubric, after proof.
- The ledger is scratch; the report is the deliverable; nothing is written inside the repository.

## References

- `references/lenses.md` — the five lenses in detail, the severity rubric, language-specific weak patterns for Swift, TS/JS, Rust, Python
- `references/report-format.md` — the report contract
- `scripts/test_inventory.py` — inventory and tier classification
- `scripts/mutation_runner.py` — detects and runs the stack's mutation tool incrementally
- `references/dispatch-prompts.md` — the auditor, prover, and verifier procedures
- the `behavioral-unit-testing` skill's `oracle-ladder.md`, when installed — what each weak tier should become
