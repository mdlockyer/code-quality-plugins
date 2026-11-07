#!/usr/bin/env python3
"""Run the stack's mutation tool incrementally on a few files and summarize survivors.

Supported: cargo-mutants (Rust), Stryker (TS/JS), muter (Swift), mutmut (Python).
Detects the tool from the repo layout and PATH; prints an install hint if the
tool is missing. Runs only on the files given (never the whole repo by default),
writes the raw tool output beside the summary, and extracts survivors with
tolerant regexes. Treat the numbers as a signal, not a target; read the
survivors.

Usage:
  python mutation_runner.py <repo> --files src/billing/invoice.py src/auth/session.py
                            [--out <ledger>/mutation.md] [--timeout 1800] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def detect(repo: Path, files: list[str]) -> tuple[str, str] | None:
    exts = {Path(f).suffix for f in files}
    if (repo / "Cargo.toml").exists() or ".rs" in exts:
        return ("cargo-mutants", "cargo install cargo-mutants")
    if (repo / "Package.swift").exists() or ".swift" in exts:
        return ("muter", "brew install muter-mutation-testing/formulae/muter")
    if (repo / "package.json").exists() or exts & {".ts", ".tsx", ".js", ".jsx"}:
        return ("stryker", "npm i -D @stryker-mutator/core (plus the vitest/jest runner plugin)")
    if (repo / "pyproject.toml").exists() or (repo / "setup.py").exists() or ".py" in exts:
        return ("mutmut", "pip install mutmut")
    return None


def available(tool: str) -> bool:
    if tool == "cargo-mutants":
        return shutil.which("cargo") is not None and subprocess.run(["cargo", "mutants", "--version"], capture_output=True).returncode == 0
    if tool == "stryker":
        return shutil.which("npx") is not None
    return shutil.which(tool) is not None


def command(tool: str, files: list[str], timeout: int) -> list[str]:
    if tool == "cargo-mutants":
        cmd = ["cargo", "mutants", "--no-shuffle", "--timeout", str(min(timeout, 600))]
        for f in files:
            cmd += ["-f", f]
        return cmd
    if tool == "stryker":
        return ["npx", "stryker", "run", "--mutate", ",".join(files), "--reporters", "clear-text,json"]
    if tool == "muter":
        # muter takes its file list from muter.conf.yml; we pass files via --filesToMutate when supported
        return ["muter", "run", "--skip-coverage", "--filesToMutate", ",".join(files)]
    if tool == "mutmut":
        return ["mutmut", "run", "--paths-to-mutate", ",".join(files), "--no-progress"]
    raise ValueError(tool)


SURVIVOR = {
    "cargo-mutants": re.compile(r"^(?:MISSED|SURVIVED)\s+(.*)$", re.M),
    "stryker": re.compile(r"^\s*\[Survived\]\s+(.*)$|^#\d+\.\s+\[Survived\].*$", re.M),
    "muter": re.compile(r"^.*(?:survived|Survived|✅ \(survived\)).*$", re.M),
    "mutmut": re.compile(r"^(?:🙁|Survived:?)\s*(.*)$", re.M),
}
SUMMARY = {
    "cargo-mutants": re.compile(r"(\d+) mutants tested.*?(\d+) caught.*?(\d+) missed", re.S),
    "stryker": re.compile(r"Mutation score.*?(\d+(?:\.\d+)?)%|All files\s*\|\s*(\d+(?:\.\d+)?)", re.S),
    "muter": re.compile(r"Mutation Score.*?(\d+)%", re.S),
    "mutmut": re.compile(r"(\d+)/(\d+).*?🎉 (\d+).*?🙁 (\d+)", re.S),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo")
    ap.add_argument("--files", nargs="+", required=True, help="production files to mutate (relative to repo)")
    ap.add_argument("--out", default="mutation.md")
    ap.add_argument("--timeout", type=int, default=1800, help="overall seconds before giving up")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    det = detect(repo, args.files)
    if not det:
        print("no supported mutation tool for this stack (cargo-mutants, stryker, muter, mutmut); record 'not run' in the ledger", file=sys.stderr)
        return 2
    tool, hint = det
    if not available(tool):
        print(f"{tool} not installed. Install: {hint}\nThen rerun. Record 'not run: {tool} unavailable' if you choose not to.", file=sys.stderr)
        return 3
    cmd = command(tool, args.files, args.timeout)
    print("running:", " ".join(cmd))
    if args.dry_run:
        return 0
    try:
        p = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=args.timeout)
        out = p.stdout + "\n" + p.stderr
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") + "\n" + (e.stderr or "") + "\n[timed out]"
    raw = Path(args.out).with_suffix(".raw.txt")
    raw.write_text(out)
    survivors = [m.group(0).strip() for m in SURVIVOR[tool].finditer(out)]
    summ = SUMMARY[tool].search(out)
    with Path(args.out).open("w") as f:
        f.write(f"# Mutation run ({tool})\n\nCommand: `{' '.join(cmd)}`\n\nFiles: {', '.join(args.files)}\n\n")
        f.write(f"Summary line: `{summ.group(0)[:200] if summ else 'not found in output; read the raw file'}`\n\n")
        f.write(f"Raw output: `{raw}`\n\n## Survivors ({len(survivors)})\n\n")
        for s_ in survivors[:200]:
            f.write(f"- {s_}\n")
        f.write("\nSurvivors are leads, not findings: the prover writes one readable mutant per unit and checks for equivalence.\n")
    print(f"wrote {args.out}: {len(survivors)} survivors extracted; raw in {raw}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
