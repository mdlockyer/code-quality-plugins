---
name: behavioral-unit-testing
description: Write tests that can actually fail — expected values from the spec, not from running the code; evidence the test fails on the bug and not only passes on the fix; no silent changes to tests; no satisfying the check instead of the request. Use whenever writing, fixing, strengthening, or reviewing tests of any kind, whenever a feature or bug fix needs tests, when a failing test tempts you to change it, when a passing test is about to be treated as proof, and when asked to "add coverage".
---

# Behavioral testing

A test exists to fail when the code is wrong. Ask four questions of every test you write or touch, and scale the effort to the stakes — a pure function with hand-computed expectations needs little; money, state, and concurrency need all of it. The user's explicit instructions override anything here.

## 1. Where did the expected value come from?

From the spec, the issue, a docstring, hand arithmetic, or a reference implementation — not from running the code and copying the output, which only confirms the code does what it does, bugs included.

- Decide scenarios and expected results before writing the code when you can; a short table is enough.
- If you can delegate, give a subagent the spec, interface, and callers but not the implementation.
- If you've already read or written the code, lean on the spec for expected values and weight question 2 more heavily. Having the buggy code in front of you measurably pulls tests toward asserting what it does; stronger models are pulled harder, not less.
- For code with no spec, write what it *should* do from docs, names, types, and callers, and test that. Where the only justification is "that's what it returns today", call it a characterization test and report any output that looks wrong instead of enshrining it.
- Where the spec is silent, decide, record the assumption in the test, and mention it. Don't settle it by running the code.

Scenarios that find bugs, in rough order: boundaries (empty, one, many, max, off-by-one, zero/negative, odd strings, month-end/DST); the specific error for each invalid input; state transitions; a happy path with hand-computed output; what must not change as a side effect. Stop when the risks are covered.

An assertion checks something when it pins an exact value, a specific error type and message, a specific resulting state, or a property over generated inputs. Non-null, truthy, didn't-throw, mock-was-called, and unreviewed snapshots pass against `return None`. Two things look strong and aren't: an expected value computed from the same formula or helper the code uses, and a patched method on the unit under test. A grep for assertion-free tests catches the first kind of weakness; only reading the test catches the other two.

## 2. How do I know it would fail on wrong code?

"The tests pass" says nothing about a test you just wrote. Think of three code states: the code without your change (the original, or the buggy version you are fixing), the code with it, and some other correct implementation a colleague might write. A test is evidence about your change only when it *fails* on the first state and passes on the second; it is a good regression test only when it would also pass on the third. Measured in repair-agent runs, nearly half of the passing checks agents collected also passed on the buggy code, and about a quarter of the ones that did fail on the bug would have rejected the developer's own fix. Both look identical from inside the loop: a green run.

So when a test passes, ask the one question the loop never asks: *would this have passed before my change?* If yes, it is regression evidence at best and says nothing about the bug or feature. Pick what fits to find out:

- **Bug fix** — run the reproducing test before the fix; keep the failure output. The failure must be an assertion with a strong oracle, not an import error, a missing symbol, or a non-null check going red because the function is new.
- **Behavior change** — revert the production change, keep the tests, run: they should fail on an assertion, not an import. With git: `git stash push -- <production paths>` (or `git diff <base> -- <paths> > p.patch && git apply -R p.patch` if the change is committed), run the tests, then `git stash pop` (or `git apply p.patch`). This proves the tests notice the change, not that they check the right thing.
- **No diff, or it matters** — break the code on purpose (flip a comparison, move a boundary by one, delete a branch, return a constant), see which test catches it, undo. One deliberate mutant is worth more than any reasoning about what a test "would" catch.
- **Mutation tool present** — run it on changed files; read the survivors on lines you touched; kill the real ones, name the equivalent ones. The score is information, not a target.
- **Only a passing characterization is possible** — write the test that pins the *buggy* output from the issue's scenario, confirm it passes on the bug, then invert the assertion to the spec'd value. The inverted test is your fail-to-pass reproduction.

Keep the test pinned to the specified behavior, not to how your fix happens to achieve it: assert the value, error, or state the spec entitles you to, not an internal call sequence or a helper your patch introduced. A test that only your patch can satisfy will block the next correct change to that code.

A print statement, a script that shows output for you to eyeball, or a run with no programmatic verdict is a probe, not a test. Probes are fine for exploring; they are not evidence, and most of what agents call "testing" mid-task is probes. Turn the probe that convinced you into an assertion before you cite it.

For trivial code it's fine to say the test is self-evidently able to fail. Say that, rather than implying you checked.

## 3. Did I change a test to make something pass?

A red test means the code is wrong until there's a concrete reason to think otherwise; say the reason before touching the test. The moves that turn a suite green without fixing anything are all easy and all look locally reasonable: deleting or skipping the test, loosening a tolerance, swapping a value for `any()`, updating the expected value to the actual one, special-casing the test inputs, overriding equality, catching the assertion, editing runner config or exit codes. If you notice yourself making one, that's the moment to stop and tell the user what you think is wrong with the test. Editing a test because the contract intentionally changed is fine — list the edit and why. Adding fixtures and helpers is fine.

## 4. Did I satisfy the check, or do the job?

An honest test can still be passed without doing what was asked. The visible check is the only part of the user's intent the code can see, so under pressure it becomes the whole spec: the behavior gets wired into whatever surface the test touches (a demo page, a fixture, a script) while the requested artifact stays hollow, or the tested inputs get a special path the real inputs never take. In a controlled study with a hidden, honest oracle, production agents drove the score to near-perfect while the requested library shipped dead or absent. They weren't cheating; they were optimizing the signal instead of the artifact.

Validate what you ship the way a user would: run the real entry point with realistic input, not only the test; check that the test exercises the thing the user asked for (the library, not the demo that imports it; the handler, not a copy of its logic in the test file); and say in your report what the checks don't cover, because that is where the work is invisible. If the only way to make the suite green is to move behavior toward the test, the suite is measuring the wrong thing — say so rather than comply.

## Craft: what agents most often get wrong

- Test through the public interface; private-helper tests break on refactors and catch nothing extra.
- One behavior per test, named for it: `test_withdrawal_exceeding_balance_is_rejected`. A test with a dozen unrelated asserts and no message (assertion roulette) tells you nothing useful when it fails.
- Literals carry their derivation in a comment (`# PAY-142: 100.00 - 10.00 = 90.00; 5% tax = 4.50`). A bare `94.50` is a magic number the next reader cannot check.
- No `if` or `try/except` in a test body — a conditional assertion passes silently. Table-driven loops over named cases are fine.
- Prefer repetition that keeps each test readable alone; extract builders, not assertion helpers.
- Use a property-based test when the spec gives you an invariant (round-trip, idempotence, order-independence, conservation, a reference model). The property must come from the spec, not the code.
- Determinism by construction: inject the clock and the seed; await conditions instead of sleeping; sort or compare as sets when order isn't specified (the top cause of flaky agent tests); no shared mutable state.
- Follow project conventions, but not its flaky or over-mocked patterns.

```python
# Checks nothing: patches the unit under test, non-null oracle, mirrors the formula
def test_apply_discount(mocker):
    mocker.patch.object(Order, "_calculate_tax", return_value=5.0)
    result = Order(subtotal=100.0).apply_discount(rate=0.10)
    assert result is not None
    assert result.total == 100.0 - (100.0 * 0.10) + 5.0

# Checks the behavior: spec-derived literal with derivation, real collaborators, side-effect invariant
def test_ten_percent_discount_applies_before_tax():
    # PAY-142: 100.00 - 10.00 = 90.00; 5% tax = 4.50; total 94.50
    order = Order(subtotal=Decimal("100.00"), tax_rate=Decimal("0.05"), items=["book"])
    discounted = order.apply_discount(rate=Decimal("0.10"))
    assert discounted.total == Decimal("94.50")
    assert discounted.items == ["book"]
```

## Test doubles

Real collaborator, then a fake with real behavior, then a stub, then a mock — each step trades fidelity for convenience, and agent-written mocks are measurably good at running and bad at matching reality. Replace only what can't run in-process (network, SDKs, clock, randomness, queues), behind a wrapper you own. Never patch the unit under test. Query code wants the real engine; if none is reachable, write the test against the real adapter, let it skip, and say the query path wasn't executed — don't mock the repository and call it tested.

## Reviewing tests

Ask the four questions of each test. Report in this order, quoting `file:test_name` with a proposed rewrite:

1. **Can't fail**: no assertion, existence-only, boolean-only, interaction-only, unreviewed snapshot, patched unit under test, expected value computed from the code's own formula.
2. **Would pass on the bug**: for a test that accompanies a fix, check whether it fails with the fix reverted; if not, it is regression evidence, not a reproduction.
3. **Enforces suspicious behavior**: expected values that look wrong, or a characterization test presented as a specification. A test that locks in a bug keeps it locked in across later commits.
4. **Pinned to one implementation**: asserts a call sequence, a private helper, or a patch-specific detail that a different correct fix would violate.
5. **Brittle or flaky**: sleeps, real clocks, unsorted collections, shared state, order dependence.

A coverage percentage is not evidence of any of this. Neither is "the agent did TDD", "it ran the tests", or a green run — those say a failure was seen, not that it was the right failure.

## Reporting

In the conversation or PR, not a notes file in the repo. Tests added/changed/removed and why; for each new test, the evidence it can fail (the red output on the pre-change code, the mutant and the test that caught it, or "self-evident"); assumptions made; anything that looked wrong and wasn't enshrined; what the real entry point did when you ran it; what's not covered. Only numbers you measured.

## References

- `references/oracle-ladder.md` — weak→strong rewrites in Python, TypeScript, Go, Java; property patterns; fail-to-pass reproduction tests.
- `references/domain-playbook.md` — async, time, randomness, databases, HTTP, UI, LLM features, CLIs, pipelines, IaC, legacy.
- `references/evidence.md` — the findings behind this, dated and caveated.
