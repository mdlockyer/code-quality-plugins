# Domain playbook

Short, concrete rules for the areas where tests most often go wrong. Read the section for whatever the code under test touches. Each section ends with the question to ask before calling the tests done.

Contents: 1 Async & concurrency · 2 Time · 3 Randomness · 4 Databases & persistence · 5 HTTP & external APIs · 6 UI · 7 LLM-backed features · 8 CLIs · 9 Data pipelines · 10 Infrastructure as code · 11 Legacy code

---

## 1. Async & concurrency

- Never wait a fixed duration. Await the thing itself: a promise, a channel, a condition (`require.Eventually`, `waitFor`, `asyncio.wait_for` with a generous timeout).
- Prefer deterministic schedulers or virtual time where the framework has them (`fake_async`, Jest fake timers with `advanceTimersByTime`, Tokio's `pause()`, Go's `synctest`).
- For true concurrency (locks, races), write one test that runs the operation N times in parallel and asserts the invariant afterwards (no lost updates, counter == N). Run it under the race detector where one exists (`go test -race`, TSAN).
- Concurrency and unordered collections are the top causes of flaky tests in industry data. Sort or use set comparison when the spec defines no order.

Ask: *If this test runs on a machine 10× slower, does it still pass? If 10× faster?*

## 2. Time

- Inject a clock (`Clock` interface, `freezegun`, `time-machine`, `jest.useFakeTimers`, `java.time.Clock.fixed`). Never call `now()` inside the unit and then assert against `now()` in the test.
- Test the calendar edges the spec cares about explicitly: month end, leap day, DST transition in the relevant zone, year boundary, midnight UTC vs local.
- Assert on specific instants or durations, never "roughly a second ago".
- Store and compare timezone-aware values; a test that passes only in the CI's timezone is a bug.

Ask: *Would this test pass at 23:59:59 on Dec 31 in a timezone with DST?*

## 3. Randomness

- Inject the RNG or seed it (`random.Random(42)`, `rand.New(rand.NewSource(1))`). Assert on exact outputs for a fixed seed *only* when the spec promises a specific algorithm; otherwise assert properties (distribution bounds, uniqueness, length).
- For property-based tests, let the framework own the seed, and record the failing seed/example as a named regression test.
- IDs, tokens, salts: assert format, length, uniqueness across N draws — not specific values.

Ask: *Does this test depend on the RNG producing a particular sequence the spec never promised?*

## 4. Databases & persistence

- Code whose job is a query gets tested against the real engine: Testcontainers, a local service in CI, or SQLite only if production is SQLite. Mocked repositories prove nothing about SQL, constraints, transactions, or ordering. If no engine is reachable from this environment (no Docker, no service), write the test against the real adapter anyway, mark it so the suite skips it where the engine is absent (`pytest.mark.skipif`, a build tag), run what you can, and say under "Not covered" that the query path was not executed here. Do not substitute a mock and call the query tested.
- Each test owns its data: transaction rollback per test, or unique keys per test, or a fresh schema. No shared seed rows that tests mutate.
- Assert the persisted state by reading it back through a separate path (raw query or a second repository instance), not by trusting the object you just saved.
- Migrations: one test that applies all migrations to an empty database and one that round-trips a representative row.
- Domain logic that merely needs *a* store may use an in-memory fake, paired with one contract test that runs the same scenarios against the real adapter.

Ask: *If the SQL had a wrong JOIN or a missing WHERE, which test fails?*

## 5. HTTP & external APIs

- Wrap every third-party client in an interface you own; test your code against a fake of that interface, and test the wrapper against the real API in a separate, clearly-marked integration suite (or recorded fixtures).
- Recorded fixtures (VCR, Polly, MSW handlers): re-record on a schedule; a two-year-old cassette tests a service that no longer exists. Keep fixtures minimal and readable.
- Consumer-driven contract tests (Pact or equivalent) between services you own. For public APIs, test the schema (OpenAPI validation) and the status codes/bodies for each documented error.
- Assert on the request that was *sent* (method, path, body, headers that matter) and the handling of each documented response class: 2xx, 4xx with error body, 5xx, timeout, malformed JSON.
- Retries and timeouts: use the injected clock; assert attempt counts and backoff, never wall-clock duration.

Ask: *Which test fails if the API starts returning 429, or an empty body with 200?*

## 6. UI

- Query the way a user would (role, label, text), not by test IDs or DOM structure (React Testing Library philosophy; Playwright's `getByRole`). Tests coupled to class names are change detectors.
- Assert user-visible outcomes: text shown, element enabled/disabled, navigation happened, request sent with the right payload (via MSW or an intercepted fetch).
- Component tests for logic and states (loading, empty, error, populated); a small number of end-to-end flows for the critical paths; visual regression only on reviewed, stable baselines.
- Snapshots: inline and small, or not at all.
- Accessibility assertions (`axe`, role/name presence) double as behavioral tests and catch real regressions.

Ask: *If the button's label changed from "Submit" to "Send", should this test fail? If the CSS class changed?*

## 7. LLM-backed features

- Split the system: everything around the model (prompt assembly, input validation, output parsing, tool routing, retries, guardrails) is deterministic code and gets normal tests with the model faked by a stub that returns *adversarial* outputs: malformed JSON, missing fields, refusals, prompt-injection strings, overlong text, wrong language.
- The model behavior itself gets *evals*, not unit tests: a versioned golden dataset of inputs with expected outcomes, scored with executable checks where possible (exact match, schema validity, contains required entities, numeric tolerance) and with a calibrated LLM judge only for fuzzy qualities. Report pass rates over N runs with a threshold; a single green run is noise.
- Never mock the LLM with a clean canonical string and call it a test of the integration; that hides prompt drift and formatting regressions.
- Pin model and prompt versions in the eval record so a regression can be attributed.
- LLM-as-judge is not a correctness oracle: it has position and self-preference biases and low test-retest reliability on code. Use it for tone, relevance, style — with periodic human calibration.

Ask: *If the model started returning valid-looking but wrong JSON, which deterministic test catches it? If the prompt were accidentally truncated, which eval drops?*

## 8. CLIs

- Test through the entry point with argv, stdin, and environment supplied explicitly; capture stdout, stderr, and exit code separately and assert all three.
- Golden-file tests for help text and formatted output are fine when small and reviewed; have an explicit, named update command and never run it to fix a failure you didn't intend.
- Filesystem effects: run in a temp directory; assert the resulting tree and file contents.
- Error paths: wrong flag, missing file, permission denied → specific exit code and specific stderr message.

Ask: *Does the test distinguish "printed the wrong thing" from "exited non-zero"?*

## 9. Data pipelines

- One small hand-built input fixture per transformation, with hand-computed expected output (rows, not row counts alone).
- Invariant tests: key uniqueness, row conservation across non-filtering steps, null policy, schema equality with a committed schema.
- Property tests for row-level pure functions (parsers, normalizers).
- Idempotence: running the job twice over the same input yields the same output and no duplicates.
- For SQL transformations, test against the real engine (section 4) with tiny tables.

Ask: *If a join silently became a cross join, which test fails?*

## 10. Infrastructure as code

- Plan/preview-level assertions (resources created, no destructive changes, required tags present) via the tool's test framework or policy-as-code.
- One ephemeral-environment integration test for the critical path (deploy, hit the health endpoint, tear down).
- Never assert on provider-generated IDs or timestamps.

Ask: *Would this test catch a change that makes the database publicly reachable?*

## 11. Legacy code with no tests

- Find the seams (Feathers): places where you can substitute a collaborator without editing the code under test. Introduce a seam (parameter, interface) with the smallest possible change before testing.
- Write characterization tests to pin current behavior *before* refactoring — but label them (`test_characterize_...` or a comment) and list every surprising output in your report instead of silently enshrining it. An LLM-generated characterization suite reliably locks in existing bugs; the label is what lets a human find them later.
- Approval/golden tests are a reasonable first net; follow with behavior tests derived from the spec as you learn it.
- Once behavior tests exist for a path, retire the characterization test for it.

Ask: *Which of these tests would I keep if the bug it currently enshrines were fixed tomorrow?*
