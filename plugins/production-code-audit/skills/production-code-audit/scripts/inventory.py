#!/usr/bin/env python3
"""Enumerate a repository for a production audit.

Produces a per-file inventory with lines of code, language, entry-point and
risk markers, maturity signals (suppressions, swallowed errors, debt markers),
and git history signals (churn, bug-fix commit count). The output is a
starting point for the orchestrator's 1-5 risk ranking; it is heuristic and
language-agnostic on purpose.

Usage:
    python inventory.py <repo> [--out inventory.json] [--md inventory.md]
                        [--since 18m] [--max-files 5000]

No third-party dependencies.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "third_party", "dist",
    "build", "out", "target", ".venv", "venv", "env", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".tox", ".next", ".nuxt", "coverage",
    ".idea", ".vscode", "bower_components", ".terraform", "Pods", ".gradle",
    "site-packages", ".cache", ".turbo", ".parcel-cache",
}
SKIP_SUFFIXES = {
    ".min.js", ".min.css", ".map", ".lock", ".sum", ".png", ".jpg", ".jpeg",
    ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".pdf", ".zip",
    ".gz", ".tar", ".jar", ".class", ".pyc", ".so", ".dll", ".dylib", ".o",
    ".a", ".bin", ".exe", ".wasm", ".mp3", ".mp4", ".mov", ".db", ".sqlite",
}
GENERATED_HINTS = ("generated", "autogen", "_pb2.py", ".pb.go", ".g.dart",
                   "__generated__", ".generated.", "_gen.go", ".d.ts")

LANG_BY_EXT = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".cjs": "javascript", ".ts": "typescript", ".tsx": "typescript", ".go": "go",
    ".rs": "rust", ".java": "java", ".kt": "kotlin", ".kts": "kotlin", ".rb": "ruby",
    ".php": "php", ".cs": "csharp", ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp",
    ".hpp": "cpp", ".swift": "swift", ".m": "objc", ".scala": "scala", ".ex": "elixir",
    ".exs": "elixir", ".erl": "erlang", ".clj": "clojure", ".dart": "dart",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell", ".sql": "sql", ".lua": "lua",
    ".pl": "perl", ".r": "r", ".jl": "julia", ".vue": "vue", ".svelte": "svelte",
    ".tf": "terraform", ".yaml": "yaml", ".yml": "yaml", ".json": "json",
    ".toml": "toml", ".ini": "ini", ".cfg": "ini", ".env": "env", ".md": "markdown",
    ".html": "html", ".htm": "html", ".css": "css", ".scss": "css", ".sol": "solidity",
    ".proto": "proto", ".graphql": "graphql", ".gql": "graphql", "Dockerfile": "docker",
    ".dockerfile": "docker", ".mk": "make", "Makefile": "make",
}
CODE_LANGS = {
    "python", "javascript", "typescript", "go", "rust", "java", "kotlin", "ruby",
    "php", "csharp", "c", "cpp", "swift", "objc", "scala", "elixir", "erlang",
    "clojure", "dart", "shell", "sql", "lua", "perl", "r", "julia", "vue",
    "svelte", "solidity",
}
CONFIG_LANGS = {"yaml", "toml", "ini", "env", "docker", "terraform", "make", "proto", "graphql"}

# Each pattern group: name -> (weight, [regexes]). Weights feed a rough score.
MARKERS: dict[str, tuple[int, list[str]]] = {
    # Where requests, jobs, and commands enter.
    "entry_point": (5, [
        r"@(app|router|api|bp|blueprint)\.(get|post|put|patch|delete|route|websocket)\b",
        r"\b(app|router|server)\.(get|post|put|patch|delete|use|all|ws)\s*\(",
        r"@(Get|Post|Put|Patch|Delete|Controller|RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping)\b",
        r"\b(HandleFunc|Handle|GET|POST|PUT|PATCH|DELETE)\s*\(\s*[\"']/",
        r"\burlpatterns\b|\bpath\s*\(\s*[\"']|\bre_path\s*\(",
        r"\bresources?\s+:[a-z_]+|\bget\s+[\"']/|\bpost\s+[\"']/|\bnamespace\s+:",
        r"@(click\.command|click\.group|app\.command|cli\.command|typer\.)",
        r"\bargparse\.ArgumentParser\b|\bcobra\.Command\b|\byargs\b|\bcommander\b|\bclap::",
        r"@(celery\.task|shared_task|task|job|cron|scheduled|Scheduled|EventListener|SqsListener|KafkaListener|RabbitListener)\b",
        r"\b(on_message|consume|subscribe|handler|lambda_handler|handle_event)\s*\(",
        r"\bwebhook\b",
        r"\bif\s+__name__\s*==\s*[\"']__main__[\"']|\bfunc\s+main\s*\(|\bfn\s+main\s*\(|\bpublic\s+static\s+void\s+main\b",
        r"\baddEventListener\s*\(|\bsignal\.signal\s*\(|\bprocess\.on\s*\(",
        r"\b(migrations?|Migration|alembic|flyway|knex\.schema)\b",
    ]),
    # Operations whose misuse is expensive.
    "risk_security": (4, [
        r"\b(auth|authn|authz|authenticate|authorize|permission|login|logout|session|jwt|oauth|token|password|passwd|credential|secret|api_key|apikey)\b",
        r"\b(hmac|sha1|sha256|md5|bcrypt|argon2|pbkdf2|AES|RSA|cipher|encrypt|decrypt|sign|verify)\b",
        r"\b(eval|exec|execfile|compile)\s*\(|\bFunction\s*\(|\bnew\s+Function\b",
        r"\bshell\s*=\s*True|\bos\.system\s*\(|\bsubprocess\.|\bchild_process\b|\bexec\.Command\b|\bProcess::Command\b|\bRuntime\.getRuntime\(\)\.exec\b",
        r"\b(pickle|marshal|yaml\.load|yaml\.unsafe_load|unserialize|ObjectInputStream|readObject|Marshal\.load)\b",
        r"\bdangerouslySetInnerHTML\b|\binnerHTML\b|\bv-html\b|\|\s*safe\b|\bmark_safe\b|\bhtml_safe\b|\braw\s*\(",
        r"\b(cursor\.execute|\.raw\(|\.query\(|sql\.text|text\(|f\"\s*SELECT|\"SELECT|'SELECT|\+\s*\"\s*(WHERE|SELECT|INSERT|UPDATE|DELETE))\b",
        r"\b(open|readFile|writeFile|os\.path\.join|path\.join|sendFile|send_file|FileResponse)\s*\(",
        r"\b(requests\.(get|post)|fetch\s*\(|axios\.|http\.Get|urllib|HttpClient)\b",
        r"\bcors\b|Access-Control-Allow-Origin",
    ]),
    "risk_money_state": (4, [
        r"\b(price|amount|balance|payment|charge|refund|invoice|billing|credit|debit|ledger|wallet|currency|checkout|subscription|stripe|paypal)\b",
        r"\b(transaction|atomic|commit|rollback|savepoint|BEGIN|COMMIT|lock|Lock|mutex|Mutex|RLock|semaphore|select_for_update|FOR UPDATE)\b",
        r"\b(retry|retries|backoff|idempoten|dedupe|deduplicat)\w*\b",
        r"\b(delete|destroy|drop|truncate|purge|remove_all|rm\s+-rf)\b",
        r"\b(cache|redis|memcache|ttl|expire)\b",
        r"\b(queue|kafka|sqs|pubsub|rabbit|celery|sidekiq|bull|worker|consumer|producer)\b",
    ]),
    "risk_parsing": (3, [
        r"\b(parse|parser|decode|deserialize|unmarshal|fromJSON|from_json|loads|load\(|Unmarshal|serde)\b",
        r"\b(regex|re\.compile|re\.match|re\.search|RegExp|regexp\.)\b",
        r"\b(struct\.unpack|ByteBuffer|bytes\.|Buffer\.|memcpy|strcpy|sprintf|strncpy|alloca)\b",
        r"\b(datetime|timezone|tzinfo|strftime|strptime|Date\(|moment\(|dayjs\(|time\.Now|chrono)\b",
        r"\b(pagination|paginate|offset|limit|cursor|page_size|next_page)\b",
    ]),
    # Signs that years-of-refinement work hasn't happened here yet.
    "suppression": (2, [
        r"#\s*noqa|#\s*type:\s*ignore|@ts-ignore|@ts-expect-error|eslint-disable|#\s*nosec|//\s*nolint|@SuppressWarnings|#\s*pragma:\s*no\s*cover|\bunsafe\b|\bas\s+any\b|\bany\b\s*[;,)]",
    ]),
    "swallowed_error": (3, [
        r"except\s*:\s*(pass|\.\.\.)?\s*$", r"except\s+(Exception|BaseException)\s*:\s*(pass|\.\.\.)?\s*$",
        r"except[^\n]*:\s*\n\s*pass\b",
        r"catch\s*\([^)]*\)\s*\{\s*\}", r"catch\s*\{\s*\}", r"\.catch\s*\(\s*\(\s*\)\s*=>\s*\{?\s*\}?\s*\)",
        r"\.catch\s*\(\s*\(?\w*\)?\s*=>\s*(null|undefined|false|\{\})\s*\)",
        r"_\s*=\s*err\b|if\s+err\s*!=\s*nil\s*\{\s*\}", r"\brescue\s*(StandardError|Exception)?\s*$",
        r"\.unwrap\(\)|\.expect\(|\bpanic\(|\bunwrap_or_default\(",
        r"\bcontinue\s*#|\bcontinue\s*//|\breturn\s+nil\s*//",
    ]),
    "debt_marker": (1, [
        r"\b(TODO|FIXME|HACK|XXX|WORKAROUND|KLUDGE|TEMP|TEMPORARY|REMOVE ME|DO NOT MERGE)\b",
    ]),
    "skipped_test": (2, [
        r"@pytest\.mark\.skip|@unittest\.skip|\bxit\(|\bxtest\(|\bxdescribe\(|\.skip\(|\.only\(|\btest\.todo\b|\bit\.todo\b|\bt\.Skip\(|@Ignore\b|@Disabled\b|\bpending\b",
    ]),
    "hardcoded_env": (2, [
        r"\blocalhost\b|127\.0\.0\.1|0\.0\.0\.0|/home/[a-z]|/Users/[A-Za-z]|C:\\\\",
        r"DEBUG\s*=\s*True|debug\s*:\s*true|NODE_ENV\s*==?\s*['\"]development",
        r"(password|secret|api_key|apikey|token|private_key)\s*[:=]\s*['\"][^'\"]{6,}['\"]",
        r"getenv\([^)]*,\s*['\"][^'\"]+['\"]\)|os\.environ\.get\([^)]*,\s*['\"][^'\"]+['\"]\)|process\.env\.\w+\s*\|\|\s*['\"]",
    ]),
    "time_handling": (1, [
        r"\b(now\(\)|today\(\)|utcnow\(\)|new\s+Date\(\)|Date\.now\(\)|time\.time\(\)|time\.Now\(\)|sleep\(|setTimeout\(|setInterval\()",
    ]),
    "concurrency": (2, [
        r"\b(threading|Thread\(|asyncio|async\s+def|goroutine|go\s+func|tokio::spawn|std::thread|CompletableFuture|ExecutorService|Promise\.all|Promise\.race|worker_threads|multiprocessing)\b",
        r"\b(global\s+\w+|static\s+\w+\s*=|@lru_cache|lru_cache\(|singleton)\b",
    ]),
}
COMPILED = {k: (w, [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in pats])
            for k, (w, pats) in MARKERS.items()}
TEST_PATH_HINTS = ("/test/", "/tests/", "/spec/", "/__tests__/", "_test.", ".test.",
                   ".spec.", "test_", "/e2e/", "/fixtures/", "/mocks/")


def is_test_file(rel: str) -> bool:
    low = rel.lower()
    return any(h in low for h in TEST_PATH_HINTS)


def is_generated(rel: str, head: str) -> bool:
    low = rel.lower()
    if any(h in low for h in GENERATED_HINTS):
        return True
    h = head.lower()
    return ("generated" in h and ("do not edit" in h or "auto-generated" in h or "autogenerated" in h))


def detect_lang(path: Path) -> str:
    if path.name in LANG_BY_EXT:
        return LANG_BY_EXT[path.name]
    return LANG_BY_EXT.get(path.suffix.lower(), "other")


def run_git(repo: Path, args: list[str]) -> str:
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                              text=True, timeout=120, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def git_signals(repo: Path, since: str) -> tuple[dict[str, int], dict[str, int], dict[str, str], list[dict]]:
    """Per-file churn (commits touching it), bug-fix commits touching it,
    last-modified date, and a sample of recent fix commits for the recon."""
    if not (repo / ".git").exists() and not run_git(repo, ["rev-parse", "--git-dir"]).strip():
        return {}, {}, {}, []
    log = run_git(repo, ["log", f"--since={since}", "--name-only", "--no-merges",
                         "--format=__C__%h%x09%ad%x09%s", "--date=short"])
    churn: Counter = Counter()
    fixes: Counter = Counter()
    last: dict[str, str] = {}
    fix_commits: list[dict] = []
    fix_re = re.compile(r"\b(fix|fixes|fixed|bug|crash|regression|hotfix|revert|broken|npe|null|race|leak|overflow|off.by.one|timezone|incorrect|wrong)\b", re.I)
    cur: dict | None = None
    for line in log.splitlines():
        if line.startswith("__C__"):
            h, date, subj = (line[5:].split("\t", 2) + ["", ""])[:3]
            cur = {"hash": h, "date": date, "subject": subj, "is_fix": bool(fix_re.search(subj)), "files": []}
            if cur["is_fix"]:
                fix_commits.append(cur)
            continue
        f = line.strip()
        if not f or cur is None:
            continue
        cur["files"].append(f)
        churn[f] += 1
        if cur["is_fix"]:
            fixes[f] += 1
        last.setdefault(f, cur["date"])
    return dict(churn), dict(fixes), last, fix_commits[:60]


def scan_file(path: Path, max_bytes: int = 2_000_000) -> dict | None:
    try:
        if path.stat().st_size > max_bytes:
            return {"too_large": True, "loc": 0}
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    lines = text.splitlines()
    loc = sum(1 for l in lines if l.strip())
    counts: dict[str, int] = {}
    samples: dict[str, list[str]] = defaultdict(list)
    for name, (_w, pats) in COMPILED.items():
        n = 0
        for p in pats:
            for m in p.finditer(text):
                n += 1
                if len(samples[name]) < 3:
                    lineno = text.count("\n", 0, m.start()) + 1
                    snippet = lines[lineno - 1].strip()[:100] if lineno - 1 < len(lines) else ""
                    samples[name].append(f"L{lineno}: {snippet}")
        if n:
            counts[name] = n
    return {"loc": loc, "markers": counts, "samples": dict(samples), "head": text[:600]}


def score(entry: dict, churn: int, fixes: int) -> float:
    s = 0.0
    for name, n in entry.get("markers", {}).items():
        w = COMPILED[name][0]
        s += w * min(n, 8) ** 0.5
    s += min(churn, 30) * 0.3 + min(fixes, 15) * 1.2
    s += min(entry.get("loc", 0), 2000) / 400.0
    if entry.get("is_test"):
        s *= 0.25
    if entry.get("generated"):
        s *= 0.1
    return round(s, 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo")
    ap.add_argument("--out", default="inventory.json")
    ap.add_argument("--md", default=None, help="also write a markdown table (default: alongside --out)")
    ap.add_argument("--since", default="18 months ago", help="git history window")
    ap.add_argument("--max-files", type=int, default=5000)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"not a directory: {repo}", file=sys.stderr)
        return 2

    churn, fixes, last, fix_commits = git_signals(repo, args.since)

    entries: list[dict] = []
    skipped = Counter()
    for root, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for fn in sorted(files):
            p = Path(root) / fn
            rel = str(p.relative_to(repo))
            if p.suffix.lower() in SKIP_SUFFIXES or fn.startswith("."):
                skipped["binary_or_dot"] += 1
                continue
            lang = detect_lang(p)
            if lang == "other":
                skipped["unknown_type"] += 1
                continue
            if len(entries) >= args.max_files:
                skipped["over_max_files"] += 1
                continue
            info = scan_file(p)
            if info is None:
                skipped["unreadable"] += 1
                continue
            e = {
                "path": rel, "lang": lang, "is_code": lang in CODE_LANGS,
                "is_test": is_test_file(rel), "generated": is_generated(rel, info.get("head", "")),
                "loc": info.get("loc", 0), "too_large": info.get("too_large", False),
                "markers": info.get("markers", {}), "samples": info.get("samples", {}),
                "churn": churn.get(rel, 0), "fix_commits": fixes.get(rel, 0),
                "last_modified": last.get(rel),
            }
            e["score"] = score(e, e["churn"], e["fix_commits"])
            entries.append(e)

    entries.sort(key=lambda e: (-e["score"], e["path"]))
    rankable = [e for e in entries if e["is_code"] or e["lang"] in CONFIG_LANGS]
    for i, e in enumerate(rankable, 1):
        e["suggested_rank"] = 5 if i <= max(5, len(rankable) // 12) else 4 if i <= len(rankable) // 5 else 3 if i <= len(rankable) // 2 else 2
        if e["is_test"] or e["generated"]:
            e["suggested_rank"] = min(e["suggested_rank"], 2)
    for e in entries:
        e.setdefault("suggested_rank", 1)

    langs = Counter(e["lang"] for e in entries)
    totals = {
        "files": len(entries), "code_files": sum(e["is_code"] for e in entries),
        "test_files": sum(e["is_test"] for e in entries),
        "loc": sum(e["loc"] for e in entries), "languages": dict(langs.most_common()),
        "skipped": dict(skipped),
        "marker_totals": dict(sum((Counter(e["markers"]) for e in entries), Counter())),
    }
    out = {"repo": str(repo), "since": args.since, "totals": totals,
           "recent_fix_commits": fix_commits, "files": entries}
    Path(args.out).write_text(json.dumps(out, indent=2))

    md_path = Path(args.md) if args.md else Path(args.out).with_suffix(".md")
    with md_path.open("w") as f:
        f.write(f"# Inventory: {repo.name}\n\n")
        f.write(f"{totals['files']} files ({totals['code_files']} code, {totals['test_files']} test), "
                f"{totals['loc']:,} LOC. Languages: " +
                ", ".join(f"{k} {v}" for k, v in langs.most_common(8)) + "\n\n")
        f.write("Marker totals: " + ", ".join(f"{k}={v}" for k, v in sorted(totals["marker_totals"].items())) + "\n\n")
        if fix_commits:
            f.write(f"## Recent bug-fix commits ({len(fix_commits)} shown, since {args.since})\n\n")
            for c in fix_commits[:25]:
                f.write(f"- `{c['hash']}` {c['date']} {c['subject'][:90]}  ({', '.join(c['files'][:3])}{', ...' if len(c['files']) > 3 else ''})\n")
            f.write("\n")
        f.write("## Files by heuristic score (suggested rank is a starting point; the orchestrator assigns the real rank)\n\n")
        f.write("| rank? | score | LOC | churn | fixes | path | markers |\n|---|---|---|---|---|---|---|\n")
        for e in entries[:400]:
            mk = ", ".join(f"{k}:{v}" for k, v in sorted(e["markers"].items(), key=lambda kv: -COMPILED[kv[0]][0]))
            flags = " (test)" if e["is_test"] else " (generated)" if e["generated"] else ""
            f.write(f"| {e['suggested_rank']} | {e['score']} | {e['loc']} | {e['churn']} | {e['fix_commits']} | `{e['path']}`{flags} | {mk} |\n")
        if len(entries) > 400:
            f.write(f"\n... {len(entries) - 400} more in {args.out}\n")
        f.write("\n## Status ledger (fill in during the audit)\n\n| unit | rank | context | hunt | repro | verify |\n|---|---|---|---|---|---|\n")
        for e in entries:
            if e["suggested_rank"] >= 4 and not e["is_test"] and not e["generated"]:
                f.write(f"| `{e['path']}` | {e['suggested_rank']} | | | | |\n")

    print(f"wrote {args.out} and {md_path}: {totals['files']} files, {totals['loc']:,} LOC, "
          f"{len(fix_commits)} fix commits in window")
    return 0


if __name__ == "__main__":
    sys.exit(main())
