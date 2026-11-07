# production_code_audit

A plugin marketplace with one plugin, **production-code-audit**: an audit that treats bug-finding as a search rather than a read. It enumerates and ranks a codebase, builds understanding records, hunts with single-question lenses, reproduces every candidate, verifies adversarially, reports with coverage, and then fixes approved findings with regression tests. Five worker agents ship alongside the orchestration skill.

The same repository is a marketplace for three hosts:

| Host | Install |
|---|---|
| Claude Code | `/plugin install production-code-audit --marketplace mdlockyer/production-code-audit` |
| Claude Cowork | Install from the marketplace above, or open `dist/production-code-audit.plugin` from a release |
| OpenAI Codex | `codex plugin marketplace add mdlockyer/production-code-audit` then `codex plugin add production-code-audit@mdlockyer-audit` |
| Google Antigravity | `agy plugin install https://github.com/mdlockyer/production-code-audit/tree/main/plugins/production-code-audit` |

Full usage, tuning, and the agent table are in [`plugins/production-code-audit/README.md`](plugins/production-code-audit/README.md).

## Repository layout

```
.claude-plugin/marketplace.json   Claude Code marketplace catalog (Codex reads this too)
.agents/plugins/marketplace.json  Codex marketplace catalog
plugins/production-code-audit/    The plugin (multi-host: Claude, Codex, Antigravity manifests side by side)
dist/                             Packaged artifacts (.plugin, .skill), not committed
```

## Validating

```
claude plugin validate .                              # marketplace
claude plugin validate ./plugins/production-code-audit
agy plugin validate ./plugins/production-code-audit  # --strict warns about the multi-host manifests by design
codex plugin marketplace add . && codex plugin list && codex plugin marketplace remove mdlockyer-audit
```

## Design notes

The methodology is distilled from how teams that find real bugs with language models actually work: Anthropic's bug-hunting scaffolds and PR review pipeline, Trail of Bits' audit skills, Cursor's Bugbot, OpenAI's Codex Security, DeepMind's CodeMender. The common shape is enumerate, examine narrowly with fresh attention, reproduce, and let a separate skeptical pass throw out what doesn't hold up. The skill's `references/` directory explains each piece and why it exists.

## License

MIT
