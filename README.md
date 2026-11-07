# code-quality-plugins

A plugin marketplace with two plugins that share one idea: a claim about code is worth nothing until something tried to falsify it.

- **production-code-audit** — an audit that treats bug-finding as a search rather than a read: enumerate and rank, build understanding records, hunt with single-question lenses, reproduce every candidate, verify adversarially, report with coverage, then fix approved findings with regression tests. Five worker agents.
- **behavioral-testing** — tests that can actually fail: writing guidance built on four questions, a test-suite audit that proves weak tests with surviving mutants, a gated repair flow, and fail-to-pass bug reproduction. Five worker agents and two hooks.

The same repository is a marketplace for three hosts:

| Host | Install |
|---|---|
| Claude Code | `/plugin install production-code-audit --marketplace mdlockyer/code-quality-plugins`<br>`/plugin install behavioral-testing --marketplace mdlockyer/code-quality-plugins` |
| Claude Cowork | Install from the marketplace above, or open `dist/production-code-audit.plugin` from a release |
| OpenAI Codex | `codex plugin marketplace add mdlockyer/code-quality-plugins` then `codex plugin add production-code-audit@mdlockyer-plugins` / `codex plugin add behavioral-testing@mdlockyer-plugins` |
| Google Antigravity | `agy plugin install https://github.com/mdlockyer/code-quality-plugins/tree/main/plugins/<plugin>` |

Full usage and the agent tables: [`plugins/production-code-audit/README.md`](plugins/production-code-audit/README.md), [`plugins/behavioral-testing/README.md`](plugins/behavioral-testing/README.md).

## Repository layout

```
.claude-plugin/marketplace.json   Claude Code marketplace catalog (Codex reads this too)
.agents/plugins/marketplace.json  Codex marketplace catalog
plugins/production-code-audit/    Multi-host plugin (Claude, Codex, Antigravity manifests side by side)
plugins/behavioral-testing/       Multi-host plugin, same layout, plus hooks/
dist/                             Packaged artifacts (.plugin, .skill), not committed
```

## Validating

```
claude plugin validate .                              # marketplace
claude plugin validate ./plugins/production-code-audit && claude plugin validate ./plugins/behavioral-testing
agy plugin validate ./plugins/production-code-audit && agy plugin validate ./plugins/behavioral-testing   # --strict warns about the multi-host manifests by design
codex plugin marketplace add . && codex plugin list && codex plugin marketplace remove mdlockyer-plugins
```

## Design notes

The methodology is distilled from how teams that find real bugs with language models actually work: Anthropic's bug-hunting scaffolds and PR review pipeline, Trail of Bits' audit skills, Cursor's Bugbot, OpenAI's Codex Security, DeepMind's CodeMender. The common shape is enumerate, examine narrowly with fresh attention, reproduce, and let a separate skeptical pass throw out what doesn't hold up. The skill's `references/` directory explains each piece and why it exists.

## License

MIT
