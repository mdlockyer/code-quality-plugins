# Test-audit report format

Written to `<ledger>/report.md` and presented in the conversation. Counts first, then what the audit covered, then findings. A reader should know in three lines whether the suite can be trusted as an oracle.

```markdown
# Test audit: <repo or path>

**<N> findings** — <h> high, <m> medium, <l> low. <k> rejected by verification, <s> unverified (appendix).
Mode: <Quick | Standard | Deep>. <One plain sentence: can this suite be trusted as an oracle, and for which units?>

## Coverage of this audit
- Test files examined: <n> of <total> (all rank 4–5<, rank 3 in Deep>). Skipped: <list with reasons, or "none">.
- Lenses run per file: <list>.
- Suite run: <command> → <pass/fail counts>. Shuffled run: <command> → <differences, or "identical">.
- Mutation run: <tool> on <units> → <killed/survived/timeout counts per unit>, or "not run: <reason>".
- Checked coverage, if measured: <n>% of executed lines have a result asserted somewhere. (Never report line coverage as evidence of quality.)
- Not covered by this audit: <e.g. E2E suites, generated tests, vendored code>.

## Units left unguarded
<The production units (rank 4–5) whose only tests are CONFIRMED can't-fail. This is the list the reader cares about most.>

## High
### T1 — <one-line title>
- **Test:** `path/test_file:test_name` (and every other location if it's a class)
- **Lens:** <1–5>
- **Guards:** <production unit and why it matters>
- **Proof:** mutant `<file:line — what was changed>` → test stayed green; output: `<the line that shows it>` | revert of <commit> → test stayed green | shuffled run → changed outcome
- **Should assert:** <the literal, error, state, or property the spec entitles it to; where the value comes from>
- **Repair move:** strengthen | untangle | escalate (lens 3: needs a human decision — test may be right and the code wrong)
- **Verifier:** KEEP high — <one line>

## Medium
...

## Low
...

## Appendix: unverified
<SPECULATIVE candidates worth a glance, one line each with what's missing.>

## Appendix: rejected
<Candidates the verifier rejected, with the reason, so the next round doesn't rediscover them.>
```

Rules:

- One finding per root cause; a weak helper used in forty tests is one finding with forty locations.
- Every finding in the main report carries a proof that can be rerun: the mutant, the revert, or the shuffle.
- Lens-3 findings never carry a recommendation to change the test; they carry the two candidate truths and ask.
- End with the question: which of these should be repaired, and in what order? Then stop.
