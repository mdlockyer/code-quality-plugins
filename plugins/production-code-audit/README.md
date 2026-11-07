# production-code-audit

Audit a codebase the way years of production use would: find the show-stoppers and the small edge-case bugs, prove each one, then fix the ones you approve with regression tests.

The goal is to make code behave like mature software, software that has been run by real users for years and had every discovered bug fixed. Most of those bugs are ordinary: the off-by-one on the last page, the retry that double-charges, the config that differs in production, the error swallowed so the user sees a spinner forever. A single agent reading a repo top-down misses them. This plugin runs the audit as a search instead: enumerate, rank, understand each unit, hunt with single-question lenses, reproduce every candidate, verify adversarially, report with coverage.

## Install

**Claude Code** (one step on 2.1.275 or later):

```
/plugin install production-code-audit --marketplace mdlockyer/code-quality-plugins
```

Or in two steps: `/plugin marketplace add mdlockyer/code-quality-plugins` then `/plugin install production-code-audit@mdlockyer-plugins`.

**Claude Cowork / Claude desktop:** download `dist/production-code-audit.plugin` from a release and open it, or install from the marketplace as above.

**OpenAI Codex:**

```
codex plugin marketplace add mdlockyer/code-quality-plugins
codex plugin add production-code-audit@mdlockyer-plugins
```

Codex defines subagents in its own TOML format. To give the audit its five workers in a repository, copy `codex/agents/*.toml` into that repository's `.codex/agents/` (or into `~/.codex/agents/` for every repository). Without them the skill still runs, using Codex's built-in `explorer` and `worker` agents for dispatch.

**Google Antigravity (agy):**

```
agy plugin install https://github.com/mdlockyer/code-quality-plugins/tree/main/plugins/production-code-audit
```

or from a clone: `agy plugin install ./plugins/production-code-audit`. The five agents load natively from `agents/`.

## What's in the plugin

**Skill: `production-code-audit`** — the orchestration procedure. Six phases, each with a coverage-based done condition, three modes (Quick, Standard, Deep), a ledger kept outside the repository, and a sequential fallback for harnesses without subagents. References cover the 14 hunting lenses, the understanding-record format, reproduction and verification rules (including exclusions, precedents, and a severity rubric), the report contract, and dispatch prompt templates. Includes `scripts/inventory.py`, a dependency-free repo enumerator with risk and git-history heuristics.

**Agents** (dispatched by the skill, one unit or finding per agent, fresh context each):

| Agent | Phase | Job |
|---|---|---|
| `audit-context-builder` | 1 | Understanding record for one unit: invariants, assumptions with what establishes them (or `nothing found`), callees walked on every path |
| `audit-hunter` | 2 | Runs lenses one at a time over one unit; every candidate needs a trigger, a line-cited path, and an impact |
| `audit-reproducer` | 3 | Makes the bug happen with a failing test, script, or sanitizer run; writes a fully cited trace when execution is impossible |
| `audit-verifier` | 4 | Tries to falsify each finding: re-reads citations, hunts for the missed check, applies precedents, re-rates severity, dedupes |
| `audit-fix-reviewer` | 6 | Reviews each applied fix for completeness, regression test validity, and anything newly introduced |

The agents are authored once in `agents/*.md` (Claude Code format, also read by Antigravity). `codex/agents/*.toml` carries the same instructions in Codex's custom-agent schema.

## Usage

Ask for an audit in whatever words come naturally: "audit this repo for production readiness", "find the bugs before we launch", "is this ready to ship", "what will break when real users hit this". The skill picks a mode from the size of the target and your phrasing; say "go deep" or mention money, auth, or a launch to get Deep mode.

The audit never edits the repository until you approve fixes. It writes its working state to a sibling directory (`../<repo>-audit/`) and presents a report that leads with counts and a coverage section. Then it stops and asks which fixes to apply.

## Tuning it to your codebase

When you reject a finding ("that's intentional", "not a problem here"), add the reason to the precedents list in `skills/production-code-audit/references/verification.md`, or to a `REVIEW.md` in your repository; the verifier reads both. That list is what keeps the signal clean over time.

To measure whether changes to the plugin help, plant known bugs in a representative repo and track recall per iteration. Three eval cases are included under `skills/production-code-audit/evals/` in the `claude plugin eval` layout.

## Requirements

- Read, grep, write, and shell access to the target repository and a scratch directory beside it.
- The project's own build and test tooling installed (the audit runs them as oracles).
- Optional: `semgrep`, `bandit`, `gosec`, `staticcheck`, or the equivalent for the stack; the audit uses whichever are present.

## Layout

```
plugins/production-code-audit/
├── .claude-plugin/plugin.json      Claude Code / Cowork manifest
├── plugin.json                     Portable Agent Plugins 1.0 manifest (Codex)
├── .codex-plugin/plugin.json       Codex compatibility overlay
├── .antigravity-plugin/plugin.json Antigravity manifest
├── skills/production-code-audit/   The orchestration skill, references, script, evals
├── agents/                         Worker agents (Claude Code and Antigravity read these)
├── codex/agents/                   The same workers as Codex custom-agent TOML
└── assets/logo.svg
```
