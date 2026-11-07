#!/usr/bin/env python3
"""Keep the standalone skills self-contained.

Agents are the single source of truth for worker procedures, but a skill installed
on its own (no plugin) cannot carry agents. This script turns each plugin's
agents/*.md bodies into references/dispatch-prompts.md inside the skills that use
those roles, so the standalone skill has the same procedure as a prompt template.
It also packages every skill as dist/<skill>.skill and every plugin as
dist/<plugin>.plugin.

Run from the repo root after editing any agent or skill:
    python3 scripts/sync_skill_dist.py
"""
from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"
DIST = ROOT / "dist"

# Which roles each skill dispatches (plugin -> skill -> [agent file stems])
ROLES = {
    "production-code-audit": {
        "production-code-audit": ["audit-context-builder", "audit-hunter", "audit-reproducer", "audit-verifier", "audit-fix-reviewer"],
    },
    "behavioral-testing": {
        "test-audit": ["test-auditor", "test-prover", "test-verifier"],
        "test-repair": ["oracle-writer", "test-repairer", "test-prover", "test-verifier"],
        "bug-repro": ["oracle-writer"],
    },
}

HEADER = """# Dispatch prompts

Worker procedures for the roles this skill dispatches. These are the same texts the plugin ships as named agents; here they are prompt templates so the skill works on its own.

How to use one: the first paragraph of each template says what the task message must give the worker (the slots). Compose a task message with those slots filled, prepend or attach the template as the worker's instructions, and send it to a fresh-context worker through whatever your harness provides (a Task/Agent tool, a spawned session, a subagent). If the harness has named agents with these roles, dispatch those instead and send only the slots. If it has no subagents at all, perform the role yourself, one unit at a time, writing each result to the ledger before starting the next, and re-reading from disk rather than memory when you move to the verification role.

Workers get fresh context on purpose. Give them facts (paths, the relevant part of recon), not your conclusions.

"""


def agent_body(plugin: str, stem: str) -> tuple[str, str]:
    text = (PLUGINS / plugin / "agents" / f"{stem}.md").read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    fm, body = m.group(1), m.group(2).strip()
    first = re.search(r"^description: \|\n  (.+)$", fm, re.M).group(1).strip()
    return first, body


def write_dispatch_prompts(plugin: str, skill: str, stems: list[str]) -> Path:
    out = PLUGINS / plugin / "skills" / skill / "references" / "dispatch-prompts.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    parts = [HEADER]
    for stem in stems:
        summary, body = agent_body(plugin, stem)
        role = stem.replace("audit-", "").replace("test-", "test ").replace("-", " ")
        parts.append(f"---\n\n## {stem} — {role}\n\n*{summary}*\n\n{body}\n\n")
    out.write_text("".join(parts).rstrip() + "\n")
    return out


def zipdir(src: Path, dest: Path, top: str | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(src.rglob("*")):
            if p.is_dir() or p.name == ".DS_Store" or "__pycache__" in p.parts:
                continue
            rel = p.relative_to(src)
            z.write(p, str(Path(top) / rel) if top else str(rel))


def main() -> int:
    for plugin, skills in ROLES.items():
        for skill, stems in skills.items():
            out = write_dispatch_prompts(plugin, skill, stems)
            print("wrote", out.relative_to(ROOT))
    DIST.mkdir(exist_ok=True)
    for plugin_dir in sorted(PLUGINS.iterdir()):
        if not plugin_dir.is_dir():
            continue
        zipdir(plugin_dir, DIST / f"{plugin_dir.name}.plugin")
        print("packaged", f"dist/{plugin_dir.name}.plugin")
        for skill_dir in sorted((plugin_dir / "skills").iterdir()):
            if (skill_dir / "SKILL.md").exists():
                zipdir(skill_dir, DIST / f"{skill_dir.name}.skill", top=skill_dir.name)
                print("packaged", f"dist/{skill_dir.name}.skill")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
