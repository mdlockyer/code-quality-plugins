# Test-audit lenses

Five single-question passes over one test file. Each is answered with candidates (`file:test_name`, the line, what it should assert instead) or `nothing applies: <reason>`. The order matters: lens 1 findings are the cheapest to prove and the most common; lens 3 findings are the most consequential and must be escalated, not fixed.

## Lens 1 — Can't fail

**Question:** For each test, what change to the production code would leave this test green?

**What a test that can fail looks like:** it pins an exact value, a specific error type and message, a specific resulting state, or a property over generated inputs, against an expectation that did not come from running the code.

**Weak forms (the tiers):**

| Tier | Looks like | Why it can't fail |
|---|---|---|
| W1 | call with no assertion; `XCTAssertNoThrow(try f())` alone; `#[test]` body ending in `.unwrap()` | catches crashes only |
| W2 | `is not None`, `toBeDefined()`, `XCTAssertNotNil`, `.is_some()` | any garbage passes |
| W3 | `assert ok`, `toBeTruthy()`, `XCTAssertTrue(valid)`, `assert!(result.is_ok())`, `#[should_panic]` without `expected` | hides what was computed |
| W4 | `assert_called_once()`, `toHaveBeenCalled()`, `XCTAssertTrue(mock.saveCalled)` as the only check | verifies wiring, not result |
| W5 | `toMatchSnapshot()` on a large or never-reviewed snapshot; a golden file nobody can derive | specifies "whatever it did last time" |

**Also can't fail, but needs reading to see:**
- The expected value is computed with the same formula, constant, or helper the production code uses (self-referential oracle).
- A method on the unit under test is patched or stubbed, so the test exercises the stub.
- A conditional or `try/except` in the test body makes the assertion skippable.
- A loop over cases where an empty case list passes vacuously.
- An assertion helper that itself cannot fail (read it).

**How to look:** every assertion line; every `mock`/`stub`/`spy`/`patch`; every `if`/`try` inside a test function; every snapshot file's size and last review.

## Lens 2 — Would pass on the bug

**Question:** For a test that was added with a fix, does it fail when the fix is reverted?

Use `git log --follow -- <test file>` to find the commit that added each test and the production files changed alongside it. For each such pair: revert the production change (stash, or `git diff <parent> -- <paths> | git apply -R`), run the test, restore. A test that stays green is regression-only: it proved the patch didn't break something, not that the bug was fixed. Nearly half of the passing checks agents collect mid-task are in this class.

Candidates name the commit, the test, and the production file, and record the revert command and output. Where the revert won't apply cleanly, record that and leave the candidate SPECULATIVE.

## Lens 3 — Enforces suspicious behavior

**Question:** Does any expected value contradict what the spec, docstring, type, name, caller, or common sense says the code should do?

**Where to look:** boundary expectations (does the test assert that index `len` is valid, that `Jan 31 + 1 month` is `Mar 3`, that a negative quantity is accepted?); error expectations (asserts that invalid input succeeds, or that a specific wrong error is thrown); rounding and money (asserts `0.1 + 0.2 == 0.30000000000000004` as if intended); characterization tests (`test_characterize_*`, "current behavior", snapshot-of-whatever-it-returned) presented as specification; tests whose expected value was visibly edited to match a later output (`git log -p` on the test shows the literal changed without the spec changing).

**Also:** the test enforces a bug that a production-audit candidate names. Cross-reference `candidates.md` from a production audit if one exists; a weak test guarding a flagged unit is a High.

**Rule:** the audit does not decide whether the test or the code is wrong. The finding says "test X asserts Y; spec/docstring/caller Z implies W" and is escalated for a human decision. Charoosaei et al. found enforced faults stay enforced across later commits; this lens is where that chain gets cut.

## Lens 4 — Pinned to one implementation

**Question:** Would a different correct implementation of the same contract fail this test?

**Looks like:** assertions on call order or call count where the contract specifies only the result; assertions on a private helper's return; `toHaveBeenCalledWith` on an internal collaborator; snapshot of internal structure; an interaction test that documents the current wiring rather than the required outcome. Also the patch-specific reproduction test: it fails on the bug and passes on this fix, but asserts a detail only this fix has (a new helper, a particular error message the spec never promised). About a quarter of agent-written fail-to-pass tests are in this class.

**Distinguish from:** interactions that *are* the contract (an audit log must be written; a webhook must be sent exactly once). Those are S2 state assertions in disguise; name them as such and move on.

## Lens 5 — Brittle or flaky

**Question:** What would make this test's result change without the code changing?

**Looks like:** `sleep`, `Task.sleep`, `setTimeout` waits, `thread::sleep`; `Date()`, `now()`, `Date.now()`, `SystemTime::now()` compared to a value computed in the test; unseeded randomness; order-dependent comparison of a collection whose order the spec leaves open (the top root cause in industry data); shared mutable state across tests (globals, class-level fixtures, env vars, temp paths without isolation); real network, real filesystem outside a temp dir, real clock; `cargo test` parallelism on shared resources; Swift tests that rely on main-actor scheduling order.

The shuffled run in phase 0 is the oracle for this lens; a test that changed outcome there is already CONFIRMED. For the rest, the prover runs the test N times or under the shuffled order to confirm.

## Severity rubric

Rate from the proof and the stakes of the unit the test guards.

| Severity | Finding |
|---|---|
| **High** | A rank-5 unit (money, auth, persistence, concurrency, data parsing) whose only tests are CONFIRMED can't-fail; a lens-3 test enforcing behavior a production audit also flagged; a regression-only test that was the sole evidence for a shipped fix; a flaky test that masks a real race |
| **Medium** | Can't-fail tests on rank-3/4 units with no stronger test covering the same path; pinned tests that will block the next refactor of a hot unit; flaky tests that have been retried or skipped in CI |
| **Low** | Redundant weak tests where a strong one also covers the path; brittle tests on stable code; W5 snapshots that are small and reviewed |

Upgrade one step for a class with many instances. Downgrade one step when a stronger test demonstrably covers the same behavior (the verifier checks).

## Language-specific weak patterns

**Swift.** `XCTAssertNoThrow` as the only assertion; `XCTAssertNotNil(try? ...)`; `XCTUnwrap` mistaken for a check; `wait(for:timeout:)` with a generous timeout masking a missing fulfillment; `@Test` functions with `#expect(x != nil)` only; `DispatchQueue.main.asyncAfter` in tests; `Task.sleep` to settle; comparing arrays from a `Set`-backed API without sorting; `@MainActor` ordering assumptions. Mutation tool: `muter`.

**TypeScript / JavaScript.** `toBeDefined()`, `toBeTruthy()`, `toHaveBeenCalled()` without args, `toMatchSnapshot()` on objects over ~20 lines, `expect.any(...)` for the value under test, `await expect(p).resolves.toBeDefined()`, `jest.mock` of the module under test, `it.skip`/`.only` committed, `setTimeout` waits, `Date.now()` without fake timers, unsorted `Object.keys`/`Map` comparison. Mutation tool: Stryker.

**Rust.** `.is_ok()`/`.is_some()`/`.is_err()` as the oracle; `#[should_panic]` without `expected`; `unwrap()` chains where the failure is a panic not an assertion; `assert!(x > 0)` where the spec gives an exact value; tests sharing a temp path or env var under default parallelism; `#[ignore]` committed. Mutation tool: `cargo-mutants`.

**Python.** `assert result`, `is not None`, `assertTrue(bool(x))`, `mock.assert_called()` only, `patch.object(Unit, ...)` on the class under test, `pytest.approx` with a wide tolerance, `except Exception: pass` in tests, `@pytest.mark.skip` without reason, `time.sleep`, unseeded `random`, set/dict iteration compared as lists. Mutation tool: `mutmut`.
