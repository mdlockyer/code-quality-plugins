#!/usr/bin/env python3
"""Inventory a test suite for a test audit.

For every test file: test count, oracle-tier counts (W1–W5 weak, S1–S3 strong),
mock density, conditionals inside test bodies, skip/focus markers, sleeps,
unsorted-collection comparisons, and the production units the file names. Writes
inventory.json and inventory.md with a weakness score and a suggested rank.

Classifies Swift (XCTest, Swift Testing), TypeScript/JavaScript (Jest, Vitest,
Mocha, node:test), Rust (#[test], proptest), and Python (pytest, unittest) well;
other languages get a coarse pass. Heuristic by design: it finds where to look,
it does not decide anything. A test with no assertion of its own that calls a
same-file helper containing strong assertions is counted as delegated (tier
suffixed "d"), not as W1; the auditor still reads the helper.

Usage: python test_inventory.py <repo> [--out inventory.json] [--md inventory.md]
No third-party dependencies.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "vendor", "target", "dist", "build", ".build", "DerivedData",
             ".venv", "venv", "__pycache__", ".tox", "coverage", "Pods", ".next", "out"}

LANG = {".swift": "swift", ".ts": "ts", ".tsx": "ts", ".js": "js", ".jsx": "js", ".mjs": "js", ".cjs": "js",
        ".rs": "rust", ".py": "python", ".go": "go", ".java": "java", ".kt": "kotlin", ".rb": "ruby"}

TEST_FILE = re.compile(
    r"(^|/)(tests?|__tests__|spec|specs|Tests|[A-Za-z0-9_]+Tests)(/|$)|"
    r"(_test\.|\.test\.|\.spec\.|/test_[^/]*\.py$|Tests?\.swift$|_tests?\.rs$|/tests\.rs$)", re.I)

# Test-function starts per language (coarse; used to split bodies)
TEST_DEF = {
    "python": re.compile(r"^\s*(async\s+)?def\s+(test_\w+)\s*\(", re.M),
    "ts": re.compile(r"^\s*(it|test)(\.(only|skip|todo|each\([^)]*\)))?\s*\(\s*(['\"`])(.*?)\4", re.M),
    "js": re.compile(r"^\s*(it|test)(\.(only|skip|todo|each\([^)]*\)))?\s*\(\s*(['\"`])(.*?)\4", re.M),
    "rust": re.compile(r"^\s*#\[(test|tokio::test|async_std::test|proptest|quickcheck)[^\]]*\]\s*(?:#\[[^\]]*\]\s*)*(?:async\s+)?fn\s+(\w+)", re.M),
    "swift": re.compile(r"^\s*(?:@Test(\([^)]*\))?\s*(?:@MainActor\s*)?func\s+(\w+)|func\s+(test\w+)\s*\()", re.M),
    "go": re.compile(r"^\s*func\s+(Test\w+)\s*\(", re.M),
    "java": re.compile(r"@Test[^\n]*\n\s*(?:public\s+)?void\s+(\w+)", re.M),
}

# Strong oracle signals (S1 value / S2 error-or-state / property)
STRONG = {
    "python": [r"assert\s+[^\n]*==", r"assertEqual\(", r"assertAlmostEqual\(", r"assertDictEqual\(", r"assertListEqual\(",
               r"pytest\.raises\(\s*\w+[^)]*match=", r"assertRaises(Regex)?\(", r"@given\(", r"assert\s+[^\n]*\bin\b"],
    "ts": [r"\.toBe\(", r"\.toEqual\(", r"\.toStrictEqual\(", r"\.toMatchObject\(", r"\.toThrow\(\s*[^)\s]", r"\.toHaveLength\(",
           r"\.toContain(Equal)?\(", r"\.toMatchInlineSnapshot\(", r"\.rejects\.toThrow\(\s*[^)\s]", r"fc\.assert\(", r"assert\.(deep)?(strict)?[Ee]qual\("],
    "rust": [r"assert_eq!\(", r"assert_ne!\(", r"assert!\(\s*matches!\(", r"#\[should_panic\(expected", r"prop_assert(_eq)?!\(", r"unwrap_err\(\)\s*,"],
    "swift": [r"XCTAssertEqual\(", r"XCTAssertNotEqual\(", r"XCTAssertThrowsError\([^)]*\)\s*\{", r"#expect\([^)]*(==|!=)",
              r"#expect\(throws:", r"XCTAssertIdentical\(", r"#require\([^)]*=="],
}
STRONG["js"] = STRONG["ts"]

# Weak oracle signals, by tier
WEAK = {
    "W2": [r"assert\s+\w+(\.\w+)*\s+is\s+not\s+None", r"assertIsNotNone\(", r"\.toBeDefined\(\)", r"\.not\.toBeNull\(\)", r"\.not\.toBeUndefined\(\)",
           r"XCTAssertNotNil\(", r"#expect\([^)]*!=\s*nil\)", r"\.is_some\(\)\s*\)", r"\.is_ok\(\)\s*\)"],
    "W3": [r"^\s*assert\s+\w+\s*$", r"assertTrue\(\s*\w+\s*\)", r"\.toBeTruthy\(\)", r"\.toBeFalsy\(\)", r"XCTAssertTrue\(\s*\w+(\.\w+)*\s*\)",
           r"XCTAssert\(\s*\w+\s*\)", r"#expect\(\s*\w+(\.\w+)*\s*\)", r"assert!\(\s*\w+(\.\w+)*(\(\))?\s*\)", r"#\[should_panic\]"],
    "W4": [r"\.assert_called(_once|_with|_once_with)?\(", r"\.toHaveBeenCalled(Times|With)?\(", r"verify\(", r"XCTAssertTrue\(\s*\w+\.\w*(called|Called|invoked)\w*",
           r"#expect\(\s*\w+\.\w*(called|Called|invoked)"],
    "W5": [r"\.toMatchSnapshot\(\)", r"\.toMatchFileSnapshot\(", r"assertSnapshot\(", r"insta::assert_snapshot!\("],
}

ASSERT_ANY = re.compile(r"\b(assert\w*|expect|XCTAssert\w*|#expect|#require|should|verify|prop_assert\w*)\b[!(]?")
MOCK = re.compile(r"\b(mock|Mock|stub|Stub|spy|Spy|patch|fake|Fake|jest\.fn|vi\.fn|sinon|mocker\.|MagicMock|when\()")
PATCH_UNIT = re.compile(r"patch(\.object)?\(\s*['\"]?(\w+)|jest\.mock\(\s*['\"](\.{1,2}/[^'\"]*)['\"]|vi\.mock\(\s*['\"](\.{1,2}/[^'\"]*)['\"]")
COND = re.compile(r"^\s*(if|elif|else if|try|except|catch|switch|match)\b", re.M)
SKIP = re.compile(r"@pytest\.mark\.skip|@unittest\.skip|\.skip\(|\.only\(|\bxit\(|\bxtest\(|\bxdescribe\(|#\[ignore\]|XCTSkip|@Test\(\.disabled|\.todo\(")
SLEEP = re.compile(r"\b(time\.sleep|asyncio\.sleep|setTimeout|Task\.sleep|thread::sleep|usleep|sleep\()")
CLOCK = re.compile(r"\b(datetime\.now|date\.today|time\.time\(|Date\.now\(|new Date\(\)|Date\(\)|SystemTime::now|Instant::now|DispatchTime\.now)")
RANDOM = re.compile(r"\b(random\.|Math\.random|rand::|thread_rng|Int\.random|\.random\(|uuid4\(|UUID\(\))")
UNSORTED = re.compile(r"(Object\.keys|Object\.values|\.keys\(\)|\.values\(\)|set\(|Set\(|HashSet|HashMap|\.collect::<Vec)[^\n]*\n[^\n]*(toEqual|assertEqual|assert_eq!|XCTAssertEqual|==)")

PROD_REF = re.compile(r"(?:from\s+([\w./]+)\s+import|import\s+[\w{}, ]+\s+from\s+['\"]([^'\"]+)['\"]|require\(['\"]([^'\"]+)['\"]\)|use\s+(crate|super)::([\w:]+)|@testable\s+import\s+(\w+)|^import\s+(\w+))", re.M)


def lang_of(p: Path) -> str:
    return LANG.get(p.suffix.lower(), "other")


def split_tests(text: str, lang: str):
    rx = TEST_DEF.get(lang)
    if not rx:
        return [("<file>", text)]
    starts = [(m.start(), m.group(0)) for m in rx.finditer(text)]
    if not starts:
        return [("<file>", text)] if ASSERT_ANY.search(text) else []
    bodies = []
    for i, (s, hdr) in enumerate(starts):
        e = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        bodies.append((hdr.strip()[:80], text[s:e]))
    return bodies


FN_DEF = re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?(?:fn|def|func)\s+(\w+)\s*[(<]|^\s*(?:const|let|function)\s+(\w+)\s*=?\s*(?:async\s*)?(?:function|\()", re.M)
CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")


def helpers(text: str) -> dict:
    """Map of same-file function name -> body (to the next definition). Coarse on purpose."""
    defs = [(m.start(), m.group(1) or m.group(2)) for m in FN_DEF.finditer(text)]
    out = {}
    for i, (s, name) in enumerate(defs):
        e = defs[i + 1][0] if i + 1 < len(defs) else len(text)
        out[name] = text[s:e]
    return out


def classify(body: str, lang: str, helper_map: dict | None = None) -> str:
    tier = _classify(body, lang)
    if tier != "W1" or not helper_map:
        return tier
    # No assertion in the test body: does it delegate to a same-file helper that asserts?
    for name in {m.group(1) for m in CALL.finditer(body)}:
        hb = helper_map.get(name)
        if hb and hb is not body:
            t = _classify(hb, lang)
            if t.startswith("S"):
                return t + "d"      # delegated strong oracle
    return tier


def _classify(body: str, lang: str) -> str:
    strong = STRONG.get(lang, STRONG["ts"])
    has_strong = any(re.search(p, body, re.M) for p in strong)
    has_any = bool(ASSERT_ANY.search(body))
    if has_strong:
        kinds = sum(1 for p in strong if re.search(p, body, re.M))
        return "S3" if kinds >= 2 else "S1"
    if not has_any:
        return "W1"
    for tier in ("W5", "W4", "W2", "W3"):
        if any(re.search(p, body, re.M) for p in WEAK[tier]):
            return tier
    return "S2"  # some assertion form we don't recognize as weak; treat as checked


def scan(path: Path, lang: str) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    tests = split_tests(text, lang)
    hmap = helpers(text)
    tiers = Counter(classify(b, lang, hmap) for _, b in tests)
    n = max(len(tests), 1)
    return {
        "tests": len(tests),
        "tiers": dict(tiers),
        "weak": sum(v for k, v in tiers.items() if k.startswith("W")),
        "mock_density": round(len(MOCK.findall(text)) / n, 2),
        "patched_targets": sorted({m.group(2) or m.group(3) or m.group(4) for m in PATCH_UNIT.finditer(text) if (m.group(2) or m.group(3) or m.group(4))})[:8],
        "conditionals_in_tests": sum(len(COND.findall(b)) for _, b in tests),
        "skips": len(SKIP.findall(text)),
        "sleeps": len(SLEEP.findall(text)),
        "real_clock": len(CLOCK.findall(text)),
        "unseeded_random": len(RANDOM.findall(text)),
        "unsorted_compare": len(UNSORTED.findall(text)),
        "covers": sorted({next(g for g in m.groups() if g) for m in PROD_REF.finditer(text)})[:12],
        "loc": sum(1 for l in text.splitlines() if l.strip()),
    }


def weakness(e: dict) -> float:
    n = max(e["tests"], 1)
    return round(
        100 * e["weak"] / n
        + 15 * min(e["mock_density"], 3)
        + 10 * min(e["conditionals_in_tests"], 5)
        + 8 * e["skips"] + 6 * e["sleeps"] + 4 * e["real_clock"] + 4 * e["unseeded_random"] + 6 * e["unsorted_compare"]
        + (20 if e["patched_targets"] else 0), 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo")
    ap.add_argument("--out", default="inventory.json")
    ap.add_argument("--md", default=None)
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    rows = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for fn in sorted(files):
            p = Path(root) / fn
            rel = str(p.relative_to(repo))
            lang = lang_of(p)
            if lang == "other" or not TEST_FILE.search(rel):
                continue
            e = scan(p, lang)
            if not e or e["tests"] == 0:
                continue
            e.update(path=rel, lang=lang)
            e["weakness"] = weakness(e)
            rows.append(e)
    rows.sort(key=lambda e: (-e["weakness"], e["path"]))
    for i, e in enumerate(rows, 1):
        e["suggested_rank"] = 5 if i <= max(3, len(rows) // 10) else 4 if i <= len(rows) // 4 else 3 if i <= len(rows) // 2 else 2
    tier_tot = sum((Counter(e["tiers"]) for e in rows), Counter())
    totals = {"files": len(rows), "tests": sum(e["tests"] for e in rows), "tiers": dict(tier_tot),
              "weak_share": round(sum(v for k, v in tier_tot.items() if k.startswith("W")) / max(sum(tier_tot.values()), 1), 3),
              "languages": dict(Counter(e["lang"] for e in rows))}
    Path(args.out).write_text(json.dumps({"repo": str(repo), "totals": totals, "files": rows}, indent=2))
    md = Path(args.md) if args.md else Path(args.out).with_suffix(".md")
    with md.open("w") as f:
        f.write(f"# Test inventory: {repo.name}\n\n{totals['files']} test files, {totals['tests']} tests. ")
        f.write("Tiers: " + ", ".join(f"{k} {v}" for k, v in sorted(tier_tot.items())) + f". Weak share: {totals['weak_share']:.0%}.\n\n")
        f.write("Weakness is a heuristic: weak-tier share, mocks, conditionals, skips, sleeps, clocks, randomness, unsorted compares, patched units. Rank is a starting point; set it from weakness × what the file guards.\n\n")
        f.write("| rank? | weakness | tests | W1 | W2 | W3 | W4 | W5 | S | deleg | mocks/test | cond | skip | sleep | file | covers |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        for e in rows[:300]:
            t = e["tiers"]; S = sum(v for k, v in t.items() if k.startswith("S") and not k.endswith("d")); D = sum(v for k, v in t.items() if k.endswith("d"))
            f.write(f"| {e['suggested_rank']} | {e['weakness']} | {e['tests']} | {t.get('W1',0)} | {t.get('W2',0)} | {t.get('W3',0)} | {t.get('W4',0)} | {t.get('W5',0)} | {S} | {D} | {e['mock_density']} | {e['conditionals_in_tests']} | {e['skips']} | {e['sleeps']} | `{e['path']}` | {', '.join(e['covers'][:4])} |\n")
        f.write("\n## Status ledger\n\n| test file | rank | hunt | prove | verify |\n|---|---|---|---|---|\n")
        for e in rows:
            if e["suggested_rank"] >= 4:
                f.write(f"| `{e['path']}` | {e['suggested_rank']} | | | |\n")
    print(f"wrote {args.out} and {md}: {totals['files']} files, {totals['tests']} tests, weak share {totals['weak_share']:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
