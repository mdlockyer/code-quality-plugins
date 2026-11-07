# Dispatch prompts

Templates for the workers the orchestrator dispatches. Fill the `<...>` slots and send the whole thing as the worker's task. Each template tells the worker what to read, what to write to the ledger, and the compact record to return. Workers are fresh-context on purpose; give them facts (paths, the relevant part of `recon.md`), not your conclusions.

If the harness has no subagents, the orchestrator performs each template itself, sequentially, writing to disk between units as the SKILL.md fallback describes.

---

## Context-builder (phase 1)

```
You are building an understanding record for one unit of code, as the first phase of a production audit. Your output feeds a bug-hunting phase that has not run yet. Produce understanding, not verdicts: do not name bugs, vulnerabilities, severities, or fixes. If you notice one, keep the observation and restate it as the structural fact it rests on.

Unit: <path> (lines <a>-<b> if partial)
Repository root: <repo>
Relevant context (from recon):
<the unit's entry points, trust boundaries, and any claims from docs/tests about what it should do>

Read the format in <skill>/references/context-record.md and follow it exactly.

The rule that matters most: follow the calls. For every function this unit calls, read it, walk every path through it (not only the success path), and record what this unit depends on it to establish. Never infer behavior from a name. For every assumption, name the line that establishes it, or write `nothing found`. No hedges: "probably" and "seems to" become a cited claim or an open question.

Write the full prose record to: <ledger>/context/<unit-id>.md
Return only the compact record (the block at the end of context-record.md), under 40 lines.
```

---

## Hunter (phase 2)

```
You are hunting for bugs in one unit of code, as part of a production audit. The standard you are comparing against is mature software: code that has been run by real users for years and had every discovered bug fixed. Find what those years would have found: the show-stoppers and the small edge cases alike.

Unit: <path>
Repository root: <repo>
Mode: <Quick | Standard | Deep>
Lenses to run, in this order: <L1, L2, ...>
Understanding record for this unit: <ledger>/context/<unit-id>.md (read it first; its "Unenforced assumptions" list is your best lead)
Relevant context from recon: <entry points reaching this unit, trust boundaries, oracle results that touch it, bug-fix history for this file>

Read <skill>/references/lenses.md. Run each listed lens as a separate pass over the unit: ask that lens's question and nothing else, trace the answers, then write the result before starting the next lens. For each lens, the result is either one or more candidates, or the literal line `nothing applies: <one-line reason>`. Do not skip a lens and do not merge passes; the separation is what gives each question your full attention.

A candidate has three required parts: the trigger (the input, state, or sequence that causes it), the path (file:line hops from trigger to impact, each line read by you and quoted), and the impact. If you cannot give all three, record it with status SPECULATIVE and one line on what's missing; do not pad it.

When a lens produces a candidate, grep the repository for the same pattern before finishing the lens and list every other location. Report the class once with all locations.

Do not report style, naming, formatting, "consider adding", or anything the project's linters already report. Do not report theoretical issues with no reachable trigger.

Write the full results to: <ledger>/findings/<unit-id>-hunt.md, one section per lens.
Append each candidate to <ledger>/candidates.md as one line:
`<id> | <unit> | <lens> | SPECULATIVE | <one-line claim> | <trigger in a few words>`
Return only: the list of candidate ids with their one-line claims, and the list of lenses that returned `nothing applies`.
```

For Deep mode's second hunter on the same unit, send the same template with the lenses in a different order and this added line: "Another hunter has examined this unit independently. Do not try to guess what they found; find what you find."

---

## Reproducer (phase 3)

```
You are trying to make a suspected bug actually happen, as part of a production audit. Your job is to turn a claim into an observation.

Candidate: <ledger>/findings/<id>.md (read it; it has the trigger, path, and impact as the hunter described them)
Repository root: <repo>
How to build and run the project and its tests: <from recon.md>
Environment constraints: <what can and cannot be executed here>

Read the reproduction standards in <skill>/references/verification.md.

Try, in order: a failing test in the project's own test framework (minimal, named after the candidate id); a script or command sequence with captured output; a sanitizer, race detector, fuzzer, or debugger run; a property-based test. Record the exact commands, the exact output, and the environment. If the reproduction works, the candidate is CONFIRMED.

If execution is impossible, write the TRACED record instead: every hop from trigger to impact as file:line with the line quoted, the precondition at each hop and what establishes it (or `nothing found`), the single hop you could not observe, and one line on why execution wasn't possible. If any hop can't be cited, the candidate stays SPECULATIVE; say which hop.

Note anything the attempt revealed that changes the severity in either direction, including partial results and dead ends.

Do not modify any file inside the repository. Tests and scripts go in <ledger>/repro/<id>/ and are referenced from the finding file.

Append your results to <ledger>/findings/<id>.md under "## Reproduction" and update the status in <ledger>/candidates.md.
Return only: `<id>: CONFIRMED | TRACED | SPECULATIVE — <one line>`.
```

Batch several cheap candidates in one dispatch when they share a build.

---

## Verifier (phase 4)

```
You are verifying a finding from a production audit. Your job is to try to make it go away. Findings survive on evidence, not on confidence, and a report with false positives gets ignored along with its true positives.

Finding: <ledger>/findings/<id>.md (read it cold; it contains the claim, the cited path, and the reproduction or trace)
Repository root: <repo>
Entry points and trust boundaries: <from recon.md>

Follow the verifier procedure in <skill>/references/verification.md:
1. Open every cited file:line and confirm it says what the finding claims. One wrong citation is a rejection.
2. Hunt for the check the hunter missed: a caller, middleware, decorator, DB constraint, framework default, type guarantee, config that is always set. Grep for it. Read the callers.
3. Re-derive the trigger: can it actually occur, who controls it, is it reachable from a listed entry point?
4. Apply the exclusions and precedents.
5. Re-rate severity with the rubric, from the evidence, not from the hunter's rating.
6. Check whether the proposed fix addresses the root cause and whether it would break documented behavior or need a dependency or migration.

Write your verdict and reasoning to the finding file under "## Verification". If REJECT, give the specific reason so it isn't rediscovered.
Return only: `<id>: KEEP <severity> | DOWNGRADE <severity>: <reason> | REJECT: <reason>`.
```

---

## Fix reviewer (phase 6)

```
You are reviewing a fix for a confirmed audit finding, with fresh context. The fix should resolve the root cause, add a regression test, and change nothing else.

Finding: <ledger>/findings/<id>.md
Diff: <path to diff, or the branch/commit>
Repository root: <repo>

Check: (1) the finding's trigger no longer produces the impact, by running the regression test and reading the changed code; (2) every location in the finding's variant list is covered, not just the first; (3) the change doesn't alter documented behavior, a public contract, or a sibling code path; (4) nothing was introduced: new unhandled error paths, new assumptions, a check added in one place that the same pattern elsewhere still lacks.

Return: `<id>: FIXED | INCOMPLETE: <what remains> | REGRESSION: <what broke>`, with file:line for anything you flag.
```
