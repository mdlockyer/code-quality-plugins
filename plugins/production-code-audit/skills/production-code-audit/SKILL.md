---
name: production-code-audit
description: "Audit a codebase the way years of production use would: find the show-stoppers and the small edge-case bugs, verify each one, then implement approved fixes. Use whenever the user asks for an audit, a review of a whole repo or module, a production-readiness or hardening pass, a bug hunt, a 'what will break' assessment, or says things like 'make this solid', 'find the bugs', 'is this ready to ship', 'what did we miss', or 'review this for issues'. Use it even for a single service or package, and even when the user does not say the word 'audit'. Not for reviewing a single PR diff (use a PR-review workflow for that)."
---

# Production Code Audit

The goal is to make the code behave like mature software: software that has been run by real users for years and had each discovered bug fixed. Most of those bugs are not exotic. They are the off-by-one in a pagination loop, the retry that double-charges, the config that differs between staging and production, the error that is swallowed so the user sees a spinner forever, the race that only shows up at 2am. A mature codebase has found and fixed those. This audit finds them now.

An audit of this kind is a **search**, not a read. The teams that find real bugs with language models (Anthropic's own bug-hunting scaffolds and PR review, Trail of Bits, Cursor's Bugbot) all converged on the same shape: enumerate the targets, rank them, examine each one narrowly with fresh attention, try to *reproduce* every candidate, and let a separate skeptical pass throw out what doesn't hold up. A single agent reading the repo top-down and writing a report is the weakest possible configuration, and it is what produces thin audits that miss things. Don't do that.

This skill therefore defines a procedure with phases, each with a *done* condition that is about coverage, not about having enough material for a report. The audit is finished when the ledger is complete, not when you feel ready to write.

## The ledger

All working state lives on disk in a scratch directory **outside the repository** (default: a sibling directory `../<repo-name>-audit/`; use a path the user gives you if they give one). Never write audit artifacts inside the repo and never commit them. The ledger exists for three reasons: your context will not survive a serious audit, subagents need somewhere to leave their results, and the user needs to see what was and wasn't covered.

```
<repo>-audit/
├── inventory.md        # every unit, its risk rank 1-5, and its status
├── recon.md            # stack, entry points, trust boundaries, oracles, history signals
├── context/<unit>.md   # one understanding record per unit (phase 1)
├── candidates.md       # every candidate issue, with status
├── findings/<id>.md    # one file per candidate: trace, reproduction, verifier verdict
└── report.md           # the deliverable
```

Candidate statuses: `CONFIRMED` (reproduced by execution), `TRACED` (full static path with every hop cited, could not execute), `SPECULATIVE` (a hunch without a path), `REJECTED` (verifier falsified it, with the reason). Only CONFIRMED and TRACED reach the main report.

## Modes

Pick a mode from the size of the target and what the user asked for, and state it in the report.

| Mode | When | What changes |
|---|---|---|
| Quick | A small package (< ~3k LOC) or the user wants a fast pass | Context records for rank-5 units only, the 4 core lenses, reproduction attempted only where a test or script is cheap (otherwise TRACED) |
| Standard (default) | A service, app, or library of normal size | Full procedure below |
| Deep | The user says production launch, money, auth, data integrity, or "find everything" | All lenses on every rank-4/5 unit, two independent hunters per unit, reproduction attempted for every candidate |

## Dispatching work

This skill is written for an orchestrator. You are the orchestrator; the phases below say which work to **dispatch** to a fresh-context worker and which to do yourself. Use whatever mechanism your harness provides for subagents (a Task/Agent tool, a worker spawn, parallel sessions). Every worker writes its full output to the ledger and returns only a short record. You read records, not prose.

**When this skill is installed as the `production-code-audit` plugin**, the workers exist as named agents and you dispatch them by name:

| Phase | Agent | Give it |
|---|---|---|
| 1 Understanding | `audit-context-builder` | unit, repo root, ledger, references dir, recon facts for the unit |
| 2 Hunt | `audit-hunter` | unit, mode, ordered lens list, context record path, recon facts, repo root, ledger, references dir |
| 3 Reproduce | `audit-reproducer` | finding file(s), how to build/run/test, environment constraints, repo root, ledger, references dir |
| 4 Verify | `audit-verifier` | finding file(s), repo root, ledger, references dir, where recon.md is |
| 6 Fix review | `audit-fix-reviewer` | finding file, the diff, repo root, how to run tests |

The agents carry their own procedures; your task message supplies only the slots above. Always include the absolute path of this skill's `references/` directory, because the agents read the formats and rules from it. **When the agents are not available** (the skill is installed standalone, or the harness has subagents but not named agents), build each worker's prompt from the templates in `references/dispatch-prompts.md` instead; they are the same procedures.

Workers get fresh context on purpose. A worker that has read the whole codebase rationalizes what it sees; a worker that has read one unit and its callees finds the gap. Keep it that way: don't paste your own conclusions into worker prompts beyond the facts in `recon.md`.

**If your harness has no subagents:** run the same phases sequentially, yourself, with these adaptations.

- Work one unit at a time and write its record to disk before starting the next. Do not hold more than one unit's worth of code in mind; re-read from the ledger when you need something.
- Run each lens as a separate deliberate pass over the unit, writing the lens's result (findings or `nothing applies`) before moving to the next lens. The separation is what makes the lenses independent; skipping it collapses back into one skim.
- Before verification, re-read each finding file cold, from disk, rather than relying on memory of having found it. Then argue against it the way the verifier template does.
- Expect this to take many turns. Give the user a one-line progress update at each phase boundary and keep going; the audit is not finished until the inventory shows every rank-4/5 unit with a status.

## Phase 0 — Recon and free oracles

Done when: `recon.md` and `inventory.md` exist, every entry point is listed, and every unit has a risk rank.

Do this yourself (it needs the whole-repo view) with help from the script.

1. Run `python <skill-dir>/scripts/inventory.py <repo> --out <ledger>/inventory.json` (in the plugin, `<skill-dir>` is `${CLAUDE_PLUGIN_ROOT}/skills/production-code-audit`); it also writes `<ledger>/inventory.md` with a ranked table and an empty status ledger to fill in. It lists every source file with LOC, language, entry-point and risk markers, suppression comments, swallowed exceptions, TODO/FIXME/HACK density, and git churn and bug-fix frequency. It is a heuristic starting point, not the ranking.
2. Establish the stack, how it's built, how it's run, how it's deployed, and what the tests look like. Read the README, build files, CI config, Dockerfiles, and the test directory layout. Note anything the project claims to guarantee (docs, docstrings, type signatures, tests): that is the intended behavior you will compare against later.
3. **Enumerate every entry point**: HTTP routes, RPC handlers, CLI commands, cron/scheduled jobs, queue and event consumers, webhooks, signal handlers, startup/shutdown hooks, migrations. Enumerate with grep and the framework's own registration patterns, not by browsing. A missed entry point is a missed audit.
4. Map trust boundaries: what is user-controlled, what is tenant-scoped, what is operator-only, what comes from other services, what is persisted and read back later (stored input is still untrusted input).
5. **Run every free oracle** the project has and record results in `recon.md`: build, type checker, test suite, linters, and whatever static analysis fits the stack (`semgrep`, `bandit`, `gosec`, `cargo clippy`, `npm audit`, `pip-audit`, `go vet`, `staticcheck`, `eslint`, `mypy`, `tsc --strict` if not already on). Install a tool if it's a one-liner. A failing build or a flaky suite is itself a finding. Oracle output also tells you what *doesn't* need a human-quality read.
6. **Mine the history**: `git log` for commits whose messages contain fix/bug/crash/regression/hotfix/revert, and which files they touch. Files that get fixed often are bug magnets, and the *kind* of fix (null checks, off-by-one, retry logic, timezone) tells you which lens to weight. Read 10–20 of those diffs; this calibrates you to the bugs this codebase actually produces.
7. Rank every unit 1–5 in `inventory.md`. A unit is a file or a cohesive module, your call, but keep units small enough to analyze in one worker. Rank 5: parses external input, handles money, auth, permissions, concurrency, persistence, or anything irreversible. Rank 1: constants, generated code, pure data. Err upward: the FreeBSD NFS bug sat in a file for 17 years because everyone assumed someone had obviously checked it.

## Phase 1 — Understanding records

Done when: every rank-4/5 unit has a `context/<unit>.md` record (Deep: rank 3 too), and `recon.md` has a consolidated list of unenforced assumptions.

Dispatch one worker per unit with the **context-builder** template. Its job is understanding, not verdicts: what the unit assumes, what it guarantees, what it depends on elsewhere, and for every assumption *what establishes it*, with a line citation, or the words `nothing found`. The format is in `references/context-record.md`.

The rule that matters most, from Trail of Bits' audit methodology: **follow the calls**. Whether a function is correct usually depends on something a callee does, and a bound looks enforced because the value came from a function whose name suggests it was checked. Workers read the callee, walk every path through it (not only the one that succeeds), and say what makes each assumption true. A precondition established on three paths out of four is an assumption, not an invariant, and the fourth path is where the bug is.

Collect every `nothing found` into `recon.md`. That list is the single best input to the hunt.

## Phase 2 — The hunt

Done when: every rank-4/5 unit has a result (findings or an explicit `nothing applies`) for every lens in the chosen mode, recorded in `candidates.md`.

Dispatch one worker per (unit, lens-group) with the **hunter** template. A lens is a single question asked of the code, defined in `references/lenses.md`. Hunters run one lens at a time and must answer each one either with candidates or with the literal `nothing applies: <one line why>`. The forced answer is what makes a pass real; "I looked at the file" is not a pass.

Lenses are grouped so a worker can run several related ones in one dispatch. In Standard mode run the core groups on every rank-4/5 unit and the applicable domain groups where the unit's role calls for them; in Deep mode run everything, and dispatch a second hunter per unit with a different lens order, since independent passes have low overlap and the union is what you want.

Every candidate goes into `candidates.md` with: id, unit, lens, one-line claim, the trigger (the input or sequence that causes it), the path (file:line hops from trigger to impact), the impact, and status `SPECULATIVE` until reproduced or traced. Hunters cite lines for every hop. A candidate whose path has an uncited hop is a hunch; record it as SPECULATIVE and move on, don't dress it up.

Hunters also have a standing instruction to look for **variants**: once a bug class is found (an unchecked length, a missing tenant filter), grep the codebase for the same pattern. Mature software fixes the class, not the instance.

## Phase 3 — Reproduce

Done when: every candidate is CONFIRMED, TRACED, or has a reproduction attempt recorded in its finding file explaining why execution wasn't possible.

Dispatch one **reproducer** per candidate (batch cheap ones). The reproducer's job is to make the bug happen: a failing unit test, a script, a `curl`, a sanitizer or race-detector run, a debugger session, a minimal input. Anything that produces an observation of the failure. Reproduction is what separates a real audit from an opinion, and it also changes severity, in both directions: the stack overflow that turns out to be unexploitable, and the "minor" validation gap that turns out to reach a `DELETE`.

A reproduction that works upgrades the candidate to CONFIRMED and the test or script is kept in `findings/<id>.md` (it becomes the regression test in phase 6). When execution is impossible (no runnable environment, external dependency), the reproducer instead produces a TRACED record: every hop from trigger to impact cited, each hop's precondition stated, and an explicit note of which hop it could not observe.

Don't skip this phase to save time. The whole reason earlier AI reviews were ignored is that they shipped unverified guesses.

## Phase 4 — Verification

Done when: every CONFIRMED and TRACED candidate has a verifier verdict in its finding file.

Dispatch a **verifier** per candidate (or per small batch), fresh context, with the template in `references/dispatch-prompts.md` and the rules in `references/verification.md`. The verifier's job is to **falsify**: find the check the hunter missed, the caller that guarantees the precondition, the framework behavior that makes it moot, the reason the "race" can't actually interleave. It re-reads every cited line and rejects the finding if any citation doesn't say what the finding claims. It applies the exclusion and precedent lists, and re-rates severity with the rubric. Findings survive on evidence, not on how confident the hunter sounded.

Verifier verdicts: `KEEP` (with severity), `DOWNGRADE` (with reason), `REJECT` (with the specific reason, which goes into the finding file so the same false positive isn't rediscovered next round). Dedupe across candidates: one finding per root cause, with all affected locations listed.

## Phase 5 — Report and wait for approval

Done when: `report.md` is written in the format in `references/report-format.md` and presented to the user.

The report leads with counts, then **coverage** (which units were examined, with which lenses, which were skipped and why, which oracles ran), then findings grouped by severity. Each finding carries its location(s), trigger, path, impact, reproduction evidence or trace, whether it's pre-existing or recently introduced (from git blame), and a proposed fix including any new dependency or breaking change. SPECULATIVE candidates go in a short appendix, clearly labeled, or are dropped if they are just noise. "No critical findings" is a legitimate result, but only when the coverage section earns it.

**Stop here and ask the user which fixes to implement.** Do not modify source files before the go-ahead. The audit phases never edit the repo; reproduction scripts and tests live in the ledger until approved.

## Phase 6 — Fix and verify

Apply approved fixes one finding at a time, each as a reviewable change. For every CONFIRMED finding, add the reproduction as a regression test in the project's test suite; that is the single most "mature software" thing an audit can leave behind. Fix the class where a variant list exists, not just the instance. Run the full suite, the type checker, and the linters after each fix, and report actual output, not "tests pass". Then run a verifier pass over the diff only, with fresh context, to check that the fix is complete and introduced nothing.

Convergence matters: don't re-audit the whole repo after fixing. Re-review only the changed code, never repeat a finding already reported, and after a third round on the same issue step back and reconsider the approach rather than patching again.

## How this audit goes wrong

These are the specific ways an audit turns thin, and the ledger exists to make each one visible:

- **Declaring done early.** The report gets written when the orchestrator has "enough", not when the inventory is covered. The done conditions above are the check; an inventory with blank status cells means the audit isn't finished.
- **Reporting hunches as findings.** A SPECULATIVE candidate dressed up with confident language. The trigger/path/impact requirement and the verifier's citation check exist to catch this.
- **Skipping the oracles.** Not running the tests, type checker, or linters because "the audit is about deeper issues". Those tools find real bugs for free and calibrate the rest of the audit.
- **Letting the script rank.** `inventory.py` scores are heuristics. A file with no markers can still be the one that handles the money.
- **`nothing applies` without reading the callees.** A hunter that answers a lens from the unit's own text, without following the calls, answers it from names. The context record's callee list is there so the hunter knows what to read.
- **Verifiers that rubber-stamp.** A verifier that re-reads the hunter's reasoning and agrees has done nothing. The verifier template is adversarial for a reason; give it the finding file, not the hunter's transcript.
- **Severity inflation.** Everything is High, so nothing is. Use the rubric after reproduction.

## Guardrails

- **No unapproved changes.** The repo is read-only until phase 6.
- **No hallucinated metrics.** Report only what was measured with the project's tools; quote the command and its output.
- **No invented citations.** Every `file:line` in a finding was read by the agent that wrote it and says what the finding claims. The verifier checks.
- **No speculative severity.** Severity follows the rubric in `references/verification.md`, after reproduction.
- **Respect the stack.** Fix within existing conventions; don't introduce major infrastructure (a cache, an observability vendor, a new framework) unless the user asks.
- **Noise is a cost.** Style, naming, formatting, "consider adding", and "best practice" without a concrete failure are not findings. If a linter could say it, the linter should say it.
- **The report is the deliverable; the ledger is scratch.** Don't leave audit documents, decision logs, or notes inside the repository.

## References

- `references/lenses.md` — the questions hunters ask, grouped, with what mature software does and where the bugs hide
- `references/context-record.md` — the understanding record format (phase 1)
- `references/verification.md` — reproduction standards, verifier rules, exclusions and precedents, severity rubric
- `references/dispatch-prompts.md` — worker prompt templates for context-builder, hunter, reproducer, verifier, fix-reviewer
- `references/report-format.md` — the report contract
- `scripts/inventory.py` — repo enumeration with risk and history heuristics
