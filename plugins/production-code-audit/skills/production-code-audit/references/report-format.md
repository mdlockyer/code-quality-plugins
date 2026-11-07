# Report format

The report is the deliverable. It is written to `<ledger>/report.md` and presented to the user in the conversation. Everything else in the ledger is scratch.

Lead with counts, then coverage, then findings. A reader should know within three lines whether there is anything urgent, and within ten whether the audit can be trusted to have looked.

```markdown
# Production audit: <repo or module>

**<N> findings** — <c> critical, <h> high, <m> medium, <l> low. <k> rejected by verification, <s> unverified (appendix).
Mode: <Quick | Standard | Deep>. <One sentence on the overall state, plainly. "No critical findings" is fine when earned.>

## Coverage
- Units examined: <n> of <total> (all rank 4–5<, all rank 3 in Deep>). Skipped: <list with one-line reasons, or "none">.
- Lenses run per unit: <list>. Lenses with no findings anywhere: <list>.
- Oracles run: <build / tests (pass/fail counts) / type checker / linters / static analysis>, with anything they reported that is not already a finding.
- History: <n> bug-fix commits reviewed; recurring classes: <e.g. "null handling in API serializers, timezone arithmetic in billing">.
- Not covered: <what this audit did not look at and why: generated code, vendored deps, UI rendering, infra-as-code, ...>.

## Critical
### C1 — <one-line title>
- **Where:** `path:line` (and every other location if it's a class)
- **Trigger:** <the input, state, or sequence>
- **Path:** <file:line → file:line → ...>, briefly
- **Impact:** <what happens, to whom>
- **Evidence:** CONFIRMED by <test name / command> — output: `<the line that shows it>` | TRACED — unobserved hop: <which>
- **Pre-existing:** yes (since <commit/date>) | introduced in <commit>
- **Fix:** <what to change, root cause not symptom>. <New dependency? Migration? Breaking change? Say so.>
- **Verifier:** KEEP critical — <one line>

## High
...

## Medium
...

## Low
...

## Appendix: unverified
<SPECULATIVE candidates worth a human's glance, one line each with what's missing. Omit the section if there are none worth listing.>

## Appendix: rejected
<Candidates the verifier rejected, one line each with the reason. This is here so the user can disagree, and so the next round doesn't rediscover them.>
```

## Rules

- One finding per root cause. A class with twelve instances is one finding listing twelve locations, not twelve findings.
- Severity comes from the verifier, not the hunter.
- No finding without evidence. If it isn't CONFIRMED or TRACED it is in the unverified appendix or nowhere.
- Write the trigger so that a developer could reproduce it from the report alone.
- Don't editorialize about code quality in general. If the codebase is in bad shape, the count and the coverage section already say so.
- End the report with the question: which of these should be fixed, and in what order? Then stop and wait.
