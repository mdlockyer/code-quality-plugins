# Understanding record (phase 1)

One record per unit, written to `<ledger>/context/<unit>.md`. The record describes what the code *is*, not what is wrong with it. Vulnerability names, severities, and fixes belong to later phases; if you find yourself writing "bug" or "vulnerable", keep the observation and restate it as the structural fact underneath it ("the length is read at L41 and used at L58 without a check in between").

The record has two halves: the prose, which is thorough and lives on disk, and the compact summary returned to the orchestrator, which is an index into the prose (never a summary of it).

## Prose format

```markdown
# <unit> — <path> (L<start>-L<end>)

**Role:** what this unit does in the system and what breaks without it.

**Entry points into this unit:** who calls it, from where, with what trust level.

## Inputs and assumptions
- `<name>` (<type>): what it is. Trust: untrusted | tenant | operator | internal.
  Established by: <file:line> or `nothing found`.
- Implicit inputs: state read, caller identity, environment, clock, config.
- Preconditions on entry: each one, and what establishes it.

## Outputs and effects
- Returns, state writes, messages/events emitted, external calls, postconditions.

## Walkthrough (block by block, where the code earns it)
### L<a>-L<b>
<the code, short>
- What it does.
- Assumes: <what must hold>, established by <file:line> or `nothing found`.
- Establishes: <invariant it creates>, depended on by <later lines or callers>.

## Cross-function dependencies
- Callee `<name>` (<internal | external-with-source | black-box>): what this unit depends on it for, on which paths. Walked: every path | only the success path (say which).
- Callers: who reaches this and what they assume it enforces.
- Shared state: what else touches the same data.

## Unenforced assumptions
A flat list of every `nothing found` above, each with the line that relies on it.

## Open questions
- unclear; need to inspect <X>
```

## Rules

**Follow the calls.** Whether this unit is correct usually depends on something a callee does. Read the callee. Walk every path through it, not just the one that returns successfully: the early return that leaves an out-parameter unset, the branch that skips the check, the loop that can exit before validating. A precondition established on three paths out of four is an assumption, and the fourth path goes in the record.

**Never infer behavior from a name.** `validate_length` may not validate anything. `safe_join` may not be safe. Read it.

**Black-box callees are adversarial.** When the source isn't available, record what is sent, what is assumed about the response, and which outcomes have not been excluded: failure, a hostile return value, a timeout, re-entry into the caller before its own writes land.

**Every claim cites a line, or becomes an open question.** No hedges: "probably", "seems to", "should be" each resolve into a cited claim or an open question.

**Depth follows the code.** Branches, calls out, state mutation, and arithmetic on sizes earn attention; three lines that copy a value earn three words. There is no minimum number of anything. A short record whose claims each cite a line beats a long one padded to fill the template.

**Say when a section is empty.** "No external calls." A missing section could mean none or never checked, and the reader can't tell which.

**Finishing with open questions is a complete record.** Finishing with open questions you never wrote down is not.

## Compact record (returned to the orchestrator)

```
unit: <path>
rank: <1-5 as given>
invariants: [<one line each, with line>]
unenforced_assumptions: [<one line each, with the line that relies on it>]
callees_not_fully_walked: [<name: reason>]
open_questions: [<one line each>]
suggested_lenses: [<lens ids this unit's shape calls for, beyond the core>]
```

The orchestrator uses `unenforced_assumptions` to seed the hunt and `suggested_lenses` to choose domain groups. Keep it under 40 lines.
