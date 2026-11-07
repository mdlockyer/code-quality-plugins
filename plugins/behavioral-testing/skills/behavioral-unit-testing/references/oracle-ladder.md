# Oracle ladder: rewriting weak assertions into strong ones

An oracle is the part of a test that knows the right answer. The ladder below is the one used in the 2026 field study of 86,000 agent-written test patches, where 80% of patches landed in the weak tiers. Each section shows the weak form and a strong rewrite. The rewrite always adds *where the expected value came from*.

Contents
1. Weak tiers (W1–W5) and why each fails
2. Rewrites: Python / pytest
3. Rewrites: TypeScript / Jest or Vitest
4. Rewrites: Go
5. Rewrites: Java / JUnit 5
5a. Rewrites: Swift / XCTest and Swift Testing
5b. Rewrites: Rust
6. Property-based tests: picking properties from the spec
7. Snapshot and golden-file tests done honestly
8. Error-contract assertions
9. Fail-to-pass reproduction tests and the three code states

---

## 1. Weak tiers

| Tier | Looks like | Why it fails |
|---|---|---|
| W1 no assertion | `service.process(order)` and nothing else | Passes unless the code throws. Catches crashes only. |
| W2 existence | `assert result is not None`, `expect(res).toBeDefined()`, `assertNotNull` | Any non-null garbage passes. `return {}` passes. |
| W3 boolean-only | `assert ok`, `expect(valid).toBeTruthy()` with no value check | Hides what was computed; `return True` passes. |
| W4 interaction-only | `mock.assert_called_once()`, `expect(fn).toHaveBeenCalled()` as the sole check | Verifies wiring. Wrong arguments, wrong result, wrong order all pass. |
| W5 snapshot-only | `expect(out).toMatchSnapshot()` with a large or never-reviewed snapshot | Specifies "whatever it did last time". Locks in bugs; updates get rubber-stamped. |

Strong tiers: S1 exact value equality against a spec-derived literal; S2 specific error / containment / state; S3 two or more strong kinds on one behavior; plus properties over generated inputs.

The question that moves an assertion up the ladder is always: *what literal, error, state, or property does the specification entitle me to assert?*

---

## 2. Python / pytest

**W2 → S1**
```python
# weak
def test_parse_duration():
    assert parse_duration("1h30m") is not None

# strong — spec: "1h30m" is 90 minutes; result is a timedelta
def test_parse_duration_hours_and_minutes():
    assert parse_duration("1h30m") == timedelta(minutes=90)
```

**W3 → S1 + S2**
```python
# weak
def test_validate_email():
    assert validate_email("a@b.co")

# strong — spec: returns the normalized address, lowercased; invalid raises ValueError naming the input
def test_validate_email_normalizes_case():
    assert validate_email("A@B.co") == "a@b.co"

def test_validate_email_rejects_missing_domain():
    with pytest.raises(ValueError, match=r"missing domain: 'a@'"):
        validate_email("a@")
```

**W4 → S2 (state) or justified interaction**
```python
# weak
def test_deactivate_user(mocker):
    repo = mocker.Mock()
    UserService(repo).deactivate(42)
    repo.save.assert_called_once()

# strong — use a fake with real state
def test_deactivate_user_marks_inactive_and_keeps_other_fields():
    repo = InMemoryUserRepo([User(id=42, email="x@y.z", active=True)])
    UserService(repo).deactivate(42)
    saved = repo.get(42)
    assert saved.active is False
    assert saved.email == "x@y.z"          # collateral invariant

# interaction IS the behavior: spec says exactly one notification, to the owner, with this subject
def test_deactivate_user_notifies_owner_once():
    mailer = RecordingMailer()
    UserService(InMemoryUserRepo([owner_user()]), mailer).deactivate(42)
    assert mailer.sent == [Mail(to="owner@y.z", subject="Account deactivated")]
```

**Self-referential oracle → literal**
```python
# weak: re-implements the formula; a shared bug passes
def test_total():
    cart = Cart([Item(price=Decimal("19.99"), qty=3)])
    assert cart.total() == Decimal("19.99") * 3 * Decimal("1.08")

# strong: hand-computed from the spec, derivation shown
def test_total_includes_eight_percent_tax():
    # 19.99 * 3 = 59.97; 8% tax = 4.7976 -> rounds half-up to 4.80; total 64.77
    cart = Cart([Item(price=Decimal("19.99"), qty=3)])
    assert cart.total() == Decimal("64.77")
```

**Parameterized boundaries**
```python
@pytest.mark.parametrize("age, expected", [
    pytest.param(17, "minor", id="one-below-threshold"),
    pytest.param(18, "adult", id="at-threshold"),
    pytest.param(0, "minor", id="zero"),
    pytest.param(150, "adult", id="upper-plausible"),
])
def test_age_category_threshold_is_eighteen(age, expected):
    assert age_category(age) == expected
```
Negative ages: if the spec is silent, do not guess from the code — write `pytest.param(-1, ..., marks=pytest.mark.xfail(reason="spec gap: negative age undefined; ask product"))` or leave it out and flag it in the report.

---

## 3. TypeScript / Jest or Vitest

**W2/W3 → S1**
```ts
// weak
it("formats price", () => {
  expect(formatPrice(1234.5)).toBeTruthy();
});

// strong — spec: two decimals, thousands separator, currency prefix
it("formats a price with thousands separator and two decimals", () => {
  expect(formatPrice(1234.5)).toBe("$1,234.50");
});
it("formats zero as $0.00", () => {
  expect(formatPrice(0)).toBe("$0.00");
});
```

**W4 → state via fake**
```ts
// weak
it("saves the draft", async () => {
  const api = { save: vi.fn().mockResolvedValue({}) };
  await new DraftStore(api).save(draft);
  expect(api.save).toHaveBeenCalled();
});

// strong — fake that holds state; assert what was persisted
it("saves the draft with a server-assigned id and keeps the body", async () => {
  const api = new FakeDraftApi();           // assigns ids 1, 2, 3...
  const store = new DraftStore(api);
  const saved = await store.save({ body: "hello" });
  expect(saved).toEqual({ id: 1, body: "hello" });
  expect(api.stored()).toEqual([{ id: 1, body: "hello" }]);
});
```

**W5 → reviewed inline snapshot of a small, intentional output**
```ts
// weak: 400-line snapshot of a whole rendered page
expect(container).toMatchSnapshot();

// strong: assert the user-visible facts
expect(screen.getByRole("heading", { name: "Order #42" })).toBeInTheDocument();
expect(screen.getByText("Total: $64.77")).toBeInTheDocument();
expect(screen.queryByRole("button", { name: "Cancel order" })).not.toBeInTheDocument(); // shipped orders can't be cancelled
```

**Error contracts**
```ts
it("rejects a transfer that exceeds the balance with INSUFFICIENT_FUNDS", async () => {
  const acct = Account.withBalance(100);
  await expect(acct.transfer(150, other)).rejects.toMatchObject({
    code: "INSUFFICIENT_FUNDS",
    message: "Balance 100.00 is less than requested 150.00",
  });
  expect(acct.balance).toBe(100);       // unchanged on failure
});
```

---

## 4. Go

```go
// weak
func TestParseConfig(t *testing.T) {
    cfg, err := ParseConfig(strings.NewReader(sample))
    if err != nil { t.Fatal(err) }
    if cfg == nil { t.Fatal("nil") }
}

// strong — table-driven, named cases, whole-value comparison, spec-derived expectations
func TestParseConfig(t *testing.T) {
    cases := []struct {
        name string
        in   string
        want Config
        wantErr string
    }{
        {name: "port and host", in: "host=a\nport=8080", want: Config{Host: "a", Port: 8080}},
        {name: "default port when omitted", in: "host=a", want: Config{Host: "a", Port: 80}},
        {name: "port out of range", in: "host=a\nport=70000", wantErr: `port 70000 out of range 1-65535`},
        {name: "empty input", in: "", wantErr: `host is required`},
    }
    for _, tc := range cases {
        t.Run(tc.name, func(t *testing.T) {
            got, err := ParseConfig(strings.NewReader(tc.in))
            if tc.wantErr != "" {
                if err == nil || err.Error() != tc.wantErr {
                    t.Fatalf("err = %v, want %q", err, tc.wantErr)
                }
                return
            }
            if err != nil { t.Fatalf("unexpected error: %v", err) }
            if diff := cmp.Diff(tc.want, got); diff != "" {
                t.Errorf("ParseConfig mismatch (-want +got):\n%s", diff)
            }
        })
    }
}
```
The `for _, tc := range cases` loop is the table, not logic: it iterates named cases and asserts the same way for each. That is the one loop the "no branching in test bodies" rule permits. Use `t.Helper()` in builders, `cmp.Diff` for whole-value equality, `t.Parallel()` only when the test owns all its state, and never `time.Sleep` to wait for goroutines (use channels, `sync.WaitGroup`, or `require.Eventually`).

---

## 5. Java / JUnit 5

```java
// weak
@Test void createsInvoice() {
    Invoice inv = service.create(order);
    assertNotNull(inv);
    verify(repo).save(any());
}

// strong — AssertJ, specific values, specific error
@Test void invoice_total_is_line_sum_plus_vat_rounded_half_up() {
    // 2 x 19.99 = 39.98; 20% VAT = 7.996 -> 8.00; total 47.98
    Order order = anOrder().withLine("book", "19.99", 2).build();

    Invoice inv = service.create(order);

    assertThat(inv.total()).isEqualByComparingTo("47.98");
    assertThat(inv.lines()).extracting(Line::description).containsExactly("book");
}

@Test void create_rejects_empty_order_with_EMPTY_ORDER() {
    assertThatThrownBy(() -> service.create(anOrder().withNoLines().build()))
        .isInstanceOf(InvalidOrderException.class)
        .hasMessage("EMPTY_ORDER: an invoice needs at least one line");
}
```
Prefer a `FakeInvoiceRepository` with an in-memory map over `@Mock InvoiceRepository` plus `verify`. Use `@ParameterizedTest` with `@CsvSource`/`@MethodSource` for boundaries, and name each case.

---

## 5a. Swift / XCTest and Swift Testing

**W2 → S1 (Swift Testing)**
```swift
// weak
@Test func parsesDuration() {
    #expect(Duration.parse("1h30m") != nil)
}

// strong — spec: "1h30m" is 90 minutes
@Test func parsesHoursAndMinutes() {
    #expect(Duration.parse("1h30m") == .seconds(90 * 60))
}
```

**W3 → S2 (XCTest error contract)**
```swift
// weak
func testInvalidEmailRejected() {
    XCTAssertFalse(Validator.isValid("a@"))
}

// strong — spec: invalid input throws .missingDomain naming the input
func testInvalidEmailThrowsMissingDomain() {
    XCTAssertThrowsError(try Validator.normalize("a@")) { error in
        XCTAssertEqual(error as? ValidationError, .missingDomain(input: "a@"))
    }
}
```

**W4 → state (Swift Testing, with a fake)**
```swift
// weak: verifies the call happened, not what was persisted
@Test func savesOrder() async {
    let store = MockStore()
    await OrderService(store: store).place(order)
    #expect(store.saveCalled)
}

// strong: in-memory fake with real behavior; assert resulting state
@Test func placingAnOrderPersistsItAsPending() async throws {
    let store = InMemoryStore()
    try await OrderService(store: store).place(.fixture(id: "o-1"))
    #expect(try store.load("o-1")?.status == .pending)   // ORD-31: new orders start pending
}
```

**Parameterized boundaries (Swift Testing)**
```swift
@Test(arguments: [
    ("", 0), ("a", 1), (String(repeating: "x", count: 255), 255), (String(repeating: "x", count: 256), 255)  // SPEC §2: cap at 255
])
func truncatesToLimit(input: String, expected: Int) {
    #expect(Label(input).text.count == expected)
}
```

Swift-specific pitfalls: `XCTAssertNoThrow` alone is W1 (prove the *value*, not just that nothing threw); `XCTUnwrap` is a precondition, not an oracle; `await`-ing on `Task.sleep` to "let things settle" is the Swift version of the fixed wait — use expectations, `confirmation(...)` in Swift Testing, or inject the clock (`ContinuousClock`/`TestClock`). Compare arrays as sets when order is unspecified; `Set` equality is cheap and deterministic.

---

## 5b. Rust

**W2 → S1 + S2**
```rust
// weak
#[test]
fn parses_amount() { assert!(parse_amount("7.50").is_ok()); }

// strong — spec: decimal string to minor units; invalid input is a typed error
#[test]
fn parses_decimal_string_to_minor_units() {
    assert_eq!(parse_amount("7.50").unwrap(), Money::minor(750));   // PAY-7: 7.50 → 750
}
#[test]
fn rejects_more_than_two_decimals() {
    assert_eq!(parse_amount("7.505").unwrap_err(), ParseError::TooManyDecimals { input: "7.505".into() });
}
```

**Property from the spec (proptest)**
```rust
proptest! {
    // SPEC: serialize/deserialize is a round trip for every valid Config
    #[test]
    fn config_round_trips(cfg in arb_config()) {
        prop_assert_eq!(Config::from_toml(&cfg.to_toml()).unwrap(), cfg);
    }
}
```

Rust-specific pitfalls: `#[should_panic]` without `expected = "..."` is W3 (any panic passes); `unwrap()` in the test body hides which step failed — prefer `?` with a descriptive error or `assert_eq!` on the `Result`; `cargo test` runs tests in parallel by default, so shared files, env vars, and global state are the flakiness source (use `tempdir`, `serial_test`, or inject). Use `cargo-mutants` for mutation runs; it works unmodified on most crates.

---

## 6. Property-based tests: picking properties from the spec

Use Hypothesis (Python), fast-check (JS/TS), `testing/quick` or `rapid` (Go), jqwik (Java), proptest (Rust). A property is worth writing when the spec hands you one of these for free:

| Property | Shape | Example |
|---|---|---|
| Round-trip | `decode(encode(x)) == x` | serializers, parsers, encoders, DB mappers |
| Idempotence | `f(f(x)) == f(x)` | normalizers, formatters, migrations |
| Invariant | `P(f(x))` always | output sorted; `len(dedupe(xs)) <= len(xs)`; money never negative |
| Conservation | some quantity preserved | sum of split payments equals the original; row count after a join with a 1:1 key |
| Commutativity / order-independence | `f(a, b) == f(b, a)` | merging, set operations, totals over a list |
| Reference model | `fast(x) == simple(x)` | optimized vs. naive implementation; new vs. old version |
| Metamorphic relation | known input change → predicted output change | adding an item never lowers a total; doubling all weights doubles the result |
| Robustness floor | never raises except documented errors | any string input to a parser |

Rules:
- Every property must be traceable to the spec or to mathematics. A property inferred by reading the implementation ("it always returns a list of the same length") is a tautology unless the spec says so.
- Constrain generators to the valid input space described by the spec, then write a separate property for how invalid inputs are rejected.
- When a property finds a failing example, add the shrunken counterexample as a named example test so the bug stays visible, and record the seed.
- Properties complement example tests; they don't replace the hand-computed happy path.

```python
from hypothesis import given, strategies as st

@given(st.lists(st.integers()))
def test_sort_output_is_ordered_permutation_of_input(xs):
    out = my_sort(xs)
    assert out == sorted(xs)                   # reference model
    assert sorted(out) == sorted(xs)           # permutation (conservation)

@given(st.text())
def test_slug_is_idempotent(s):
    assert slugify(slugify(s)) == slugify(s)
```

---

## 7. Snapshot and golden-file tests done honestly

Acceptable when: the output is small enough to review in a diff, it is reviewed and committed deliberately, and a human can say *why* each part is right. Required practice:
- Prefer inline snapshots (`toMatchInlineSnapshot`, `insta` in Rust, `assert_snapshot`) so the expected value sits in the test.
- Add at least one explicit assertion on the facts that matter most, so the test still fails meaningfully if the snapshot is deleted.
- Never run the "update snapshots" command to make a failing test pass unless the change was intentional and you say so in the report.

---

## 8. Error-contract assertions

An error assertion is strong only when it pins the *specific* contract: type **and** message/code (or a structured error field), plus the state after the failure.

```python
with pytest.raises(InsufficientFunds) as exc:
    account.withdraw(Decimal("150"))
assert exc.value.requested == Decimal("150")
assert exc.value.available == Decimal("100")
assert account.balance == Decimal("100")   # unchanged
```

`pytest.raises(Exception)`, `assertThrows(Throwable.class)`, `expect(...).toThrow()` with no message are W-tier: they pass for a `TypeError` caused by a bug in the error path itself.

---

## 9. Fail-to-pass reproduction tests and the three code states

A reproduction test is judged on three code states, not one:

| State | What the test should do | If it doesn't |
|---|---|---|
| **B** — the code before the fix (the bug) | Fail, on an assertion, with a strong oracle | The test is *regression-only*: it proves nothing about the bug. Nearly half of the passing checks agents collect mid-task are in this class. |
| **S** — the code with your fix | Pass | Your fix is incomplete, or the test asserts the wrong thing. |
| **G** — any other correct fix | Pass | The test is *candidate-specific*: pinned to your implementation, it will reject the next correct change. About a quarter of agent tests that fail on B are in this class. |

Reaching all three: derive the expected value from the issue or spec (question 1), run on B and keep the red output (question 2), and assert the specified value, error, or state rather than a call sequence or a helper your patch added.

**Weak red → strong red (Python)**
```python
# weak: goes red on B because the symbol is new, not because the behavior is wrong
def test_parse_handles_leading_zero():
    from money import parse_amount_v2     # ImportError on B
    assert parse_amount_v2("007.50") is not None

# strong: same public entry point on B and S; the failure on B is the actual bug
def test_parse_amount_accepts_leading_zero():
    # BUG-88: "007.50" must parse as 7.50, not raise
    assert parse_amount("007.50") == Decimal("7.50")
```

**Candidate-specific → spec-aligned (TypeScript)**
```ts
// candidate-specific: asserts the helper the patch introduced; a fix that inlines the logic fails this
it("normalizes via normalizeEmail", () => {
  const spy = vi.spyOn(util, "normalizeEmail");
  register("A@B.co");
  expect(spy).toHaveBeenCalledWith("A@B.co");
});

// spec-aligned: asserts the observable result the issue described
it("stores registered emails lowercased", async () => {
  await register("A@B.co");                 // ISSUE-212: emails are case-insensitive
  expect(await findUser("a@b.co")).toMatchObject({ email: "a@b.co" });
});
```

**Inversion when only a characterization is possible.** When you can't derive the expected value cleanly, write the test that pins the *buggy* output for the issue's scenario, confirm it passes on B, then flip the assertion to the value the spec implies. The flipped test fails on B and is your fail-to-pass reproduction; the derivation comment records why the new value is right.

**Probe → test.** `print(result)` and a script you read by eye are probes. The one that convinced you becomes the assertion: same inputs, the value you saw was wrong replaced by the value the spec requires.

