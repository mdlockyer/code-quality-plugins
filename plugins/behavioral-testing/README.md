# behavioral-testing

Tests that can actually fail. Four skills, five agents, and two hooks built on one discipline: a test exists to fail when the code is wrong, and most agent-written tests never would.

## Install

**Claude Code** (one step on 2.1.275 or later):

```
/plugin install behavioral-testing --marketplace mdlockyer/code-quality-plugins
```

**OpenAI Codex:**

```
codex plugin marketplace add mdlockyer/code-quality-plugins
codex plugin add behavioral-testing@mdlockyer-plugins
```

Codex subagents use its own TOML format: copy `codex/agents/*.toml` into the repository's `.codex/agents/` (or `~/.codex/agents/`) to give the audit and repair flows their workers.

**Google Antigravity (agy):**

```
agy plugin install https://github.com/mdlockyer/code-quality-plugins/tree/main/plugins/behavioral-testing
```

Hooks ship enabled. Antigravity and Codex ask you to trust plugin hooks on first use; both hooks are read-only Python scripts that only ever add a note to the conversation.

## What's in it

| Skill | Mode | What it does |
|---|---|---|
| `behavioral-unit-testing` | writing (ambient) | The four questions for any test you write or touch: where did the expected value come from; how do you know it fails on wrong code; did you change a test to pass; did you satisfy the check or do the job. Oracle ladder and domain playbook for Swift, TS/JS, Rust, Python. |
| `test-audit` | audit | A search over the suite: inventory and rank, run the suite shuffled, run a mutation tool on top-ranked units, hunt each file with five lenses, prove every weak test with a surviving mutant, verify adversarially, report with coverage, stop for approval. |
| `test-repair` | repair | Three named moves for approved findings (strengthen, untangle, escalate), each with proof produced by a different agent than the one that edited. Expected values come from a spec-only oracle-writer, never from running the code. Tests that enforce suspicious behavior are escalated to a human, not rewritten. |
| `bug-repro` | reproduce | Issue in, fail-to-pass test out, judged on three states: fails on the bug on an assertion, passes on the fix, would pass on any other correct fix. |

| Agent | Job |
|---|---|
| `test-auditor` | One test file, five lenses, read-only, candidates with `file:test_name` and the line |
| `test-prover` | Breaks the production code deliberately, runs the test, records the output, restores; proves repairs the same way |
| `oracle-writer` | Derives expected values from spec, docstrings, callers, and arithmetic without reading the implementation |
| `test-repairer` | The only agent that edits tests; one finding, one diff, derivation on every literal |
| `test-verifier` | Fresh-context falsification of findings and repairs: re-runs the mutant, checks for another test that catches it, checks that no expectation was taken from the code |

| Hook | When | What |
|---|---|---|
| passing-test reminder | after a test command passes | Adds one question to the context: would this have passed before your change? (A plain reminder at this moment accounted for a third of the improvement in bug-discriminating evidence in Xu & Wu 2026.) |
| test-edit guard | after an edit to a test file | Names any of the moves that turn a suite green without fixing anything (`.skip`, `.only`, `XCTSkip`, `#[ignore]`, wildcards, loosened tolerances, caught or removed assertions, runner settings) and asks for the reason before continuing. Never blocks. |

## Why

The research the plugin stands on is in `skills/behavioral-unit-testing/references/evidence.md`, dated and caveated. The short version: 80% of agent test patches have weak or no oracle; tests written with the buggy code visible detect roughly half as many faults; nearly half of the passing checks agents collect also pass on the bug; a quarter of the ones that do fail on the bug would reject a correct alternative fix; agents with test access satisfy honest oracles by building to the test; and mutation testing is the only cheap check that sees through all of it.

## Works with

`production-code-audit` (same marketplace) uses `bug-repro` for its reproduction phase and `test-auditor` for its "can the tests fail?" lens when this plugin is installed, and falls back to its own compact rules when it isn't.

## Layout

```
plugins/behavioral-testing/
├── .claude-plugin/plugin.json       Claude Code / Cowork manifest
├── plugin.json                      Portable Agent Plugins 1.0 manifest (Codex)
├── .codex-plugin/plugin.json        Codex compatibility overlay
├── .antigravity-plugin/plugin.json  Antigravity manifest
├── skills/                          behavioral-unit-testing, test-audit, test-repair, bug-repro
├── agents/                          five workers (Claude Code and Antigravity read these)
├── codex/agents/                    the same workers as Codex custom-agent TOML
├── hooks/                           hooks.json + two scripts
└── assets/logo.svg
```
