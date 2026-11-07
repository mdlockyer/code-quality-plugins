# Verification

Two separate steps, done by separate workers: **reproduce** (make the bug happen) and **verify** (try to make the finding go away). The first establishes that the behavior is real; the second establishes that it matters and that the write-up is accurate. Keep them separate because the reproducer is motivated to succeed and the verifier is motivated to reject, and you want both pressures.

## Reproduction standards

A candidate becomes **CONFIRMED** when execution produced an observation of the failure. Acceptable evidence, in order of preference:

1. A failing test added in the project's own test framework (this becomes the regression test in phase 6). Keep it minimal and name it after the finding id.
2. A script or command sequence (`curl`, a REPL session, a CLI invocation) with its captured output showing the failure.
3. A sanitizer, race detector, fuzzer, or debugger observation (ASan/UBSan/TSan output, `go test -race`, a Hypothesis/fast-check counterexample, a breakpoint showing the bad state).
4. A property-based or differential test demonstrating the divergence.

Record the exact command, the exact output, and the environment (version, config) in `findings/<id>.md`. "I ran it and it failed" without output is not evidence.

A reproduction *test* (the preferred evidence) is judged on three code states, and the finding file records all three:

- **Current code:** the test fails on an assertion with a strong oracle (an exact value, a specific error, a resulting state). An import error, a missing symbol, a crash on `None`, or a non-null check going red is not a reproduction.
- **Expected value:** derived from the spec, docstring, type, callers, issue, or hand arithmetic, and written down before the test is run. Never from running the code: that is the bug's output. If only a characterization is possible, write the test that pins the buggy output, confirm it passes, then invert the assertion to the specified value.
- **Any correct fix:** the test asserts the behavior the contract promises, not the fix the hunter proposed. If it names a helper that doesn't exist yet or a call sequence the spec never required, it is pinned to one implementation and will block the next correct change; loosen it to the contract while keeping it strong.

When the `bug-repro` skill is available in the session, the reproducer follows it; it is the full version of these rules.

A candidate becomes **TRACED** when execution was not possible (no runnable environment, requires production data, external dependency) and the reproducer instead wrote the full static path:

- Every hop from trigger to impact as `file:line`, quoted.
- At each hop, the precondition for continuing and why it holds (or `nothing found` if nothing establishes it).
- The one hop the reproducer could not observe directly, named explicitly.
- Why execution wasn't possible, in one line.

A TRACED finding with an uncited hop, or a hop whose quoted line doesn't say what the trace claims, is not TRACED. It goes back to SPECULATIVE.

Reproduction changes severity in both directions. The stack overflow may be unreachable; the "minor" missing filter may reach a delete. Note what the reproduction attempt revealed even when it failed.

## Verifier rules

The verifier reads the finding file cold, with fresh context, and tries to **reject** it. It has not seen the hunter's reasoning beyond what's in the file, and it should not be given it.

Procedure:

1. **Re-read every cited line.** Open the file, go to the line, confirm it says what the finding claims. One wrong citation rejects the finding (the hunter can re-submit with correct citations, but the verifier doesn't fix it for them).
2. **Look for the missing check.** Is the precondition enforced by a caller, a middleware, a decorator, a database constraint, a framework default, a type system guarantee, a config that is always set, a deployment constraint? Grep for the guard the hunter may have missed. Read the callers.
3. **Re-derive the trigger.** Can the described input or sequence actually occur? Who controls it? Is it reachable from an entry point in `recon.md`? "An attacker who already has admin" is usually not a trigger.
4. **Apply the exclusions and precedents** below. They encode what experienced reviewers have learned not to report.
5. **Re-rate severity** with the rubric below, from the reproduction evidence, not from the hunter's rating.
6. **Dedupe.** If this is the same root cause as another finding, merge: one finding, all locations.
7. **Check the fix.** Does the proposed fix address the root cause or the symptom? Would it break a documented behavior? Does it need a new dependency or a migration?

Verdicts: `KEEP <severity>`, `DOWNGRADE <severity>: <reason>`, `REJECT: <specific reason>`. The reason for a rejection is written into the finding file so the same false positive isn't rediscovered in a later round. Verifiers that reject everything are as useless as hunters that find everything; the standard is "would a senior engineer who knows this codebase confidently raise this?"

## Exclusions (do not report, in any mode)

- Style, naming, formatting, import order, comment quality, "could be simplified".
- "Consider adding" (logging, docs, tests, types, validation) without a concrete failure that the absence causes. Missing tests are reported only for a CONFIRMED bug that a test would have caught, as part of that finding.
- Theoretical issues with no reachable trigger from an entry point.
- Denial-of-service from missing rate limiting, by itself. (An unbounded allocation from a single small request is different, and is in scope under L8.)
- Vulnerabilities in third-party dependencies, except: a known-vulnerable version of a direct dependency that the project actually exercises on the vulnerable path, which is one finding listing all of them.
- Memory-safety findings in memory-safe languages outside `unsafe`/FFI/`ctypes` blocks.
- Client-side permission checks being absent; the server is responsible. (The server missing them is L5.)
- Secrets management policy ("should use a vault") when the secret is already read from the environment. A secret committed in the repo *is* a finding.
- Log injection / log spoofing; logging non-secret, non-PII data.
- Anything a linter in the project already reports (report instead that the linter output is being ignored, once).
- Hypothetical performance issues without a measurement or a reasoned bound tied to realistic data size.

## Precedents (judgment calls already made)

- Environment variables, CLI flags, and config files are trusted inputs. An attack that requires controlling them is not a finding, but a *default* value in one of them that is unsafe for production is (L9).
- UUIDv4 identifiers are unguessable. Sequential integer IDs exposed to users are not a finding by themselves, but are a finding when combined with a missing ownership check (L5).
- Data read back from the project's own database is still untrusted if it was originally user-supplied (stored XSS, second-order injection).
- An HTTP 200 with an error body from an external API, when the code only checks the status, is a real failure path (L2/L11).
- `except Exception: log; continue` in a batch loop is a finding only if it leaves state inconsistent or hides a failure the user needs to know about; it is not a finding when the loop is explicitly best-effort and the failure is recorded.
- A race condition is a finding when the two interleaving operations are both reachable in normal use and the outcome is a lost update, duplicate, or inconsistency. A race that requires sub-microsecond timing on a single-threaded code path is not.
- Floating point for money or quantities that are summed, compared for equality, or persisted is a finding. Floating point for a progress percentage is not.
- A `TODO` is not a finding. The incomplete behavior it describes may be.
- A missing timeout on an outbound call is a finding when the call is on a request path or holds a connection/lock; it is noise on a one-off CLI.
- A test that asserts incorrect behavior is a finding (it locks the bug in). A missing test is not.
- Pre-existing bugs are still findings; tag them `pre-existing` (from git blame) so the report doesn't read as blame for whoever touched the file last.

Grow this list. When the user responds to a finding with "that's intentional" or "not a problem here", add the reason as a precedent so the next audit of this codebase doesn't repeat it. Keep project-specific precedents in the user's `REVIEW.md`/`CLAUDE.md` if they maintain one, not in this file.

## Severity rubric

Rate from the reproduced or traced impact, then adjust for reachability. Reachability means: who can trigger it and how much they need (nothing / a normal account / a privileged account / a specific unusual state).

| Severity | Impact (any one) |
|---|---|
| **Critical** | Unauthenticated or cross-tenant access to data or actions; remote code execution; data loss or corruption that cannot be recovered from backups; money moved incorrectly; a crash or hang reachable by any user with a single request |
| **High** | Authenticated privilege escalation or access to other users' data; corruption recoverable only by manual intervention; a failure path that leaves persistent state inconsistent; a crash reachable by a normal user through normal use; an outage mode triggered by a dependency failure with no degradation |
| **Medium** | Incorrect results on realistic inputs (the off-by-one, the timezone bug, the wrong sort) that users would notice and report; a race producing duplicates or lost updates under normal load; a failure the user cannot recover from without support; a resource leak that degrades over hours |
| **Low** | Incorrect results on unusual but legitimate inputs; a confusing or misleading failure message; a defensive gap with no current trigger but a clear path to one on the next change; operability gaps that will make the next incident slower to resolve |

Downgrade one step when the trigger requires a privileged principal or an unusual state that normal use does not produce. Upgrade one step when the finding is a class with many instances. Don't inflate: a report full of Highs that are Mediums gets ignored, and then the real High gets ignored with it.
