#!/usr/bin/env python3
"""PostToolUse hook: after an edit to a test file, flag the moves that turn a
suite green without fixing anything.

Skipping or focusing tests, loosening tolerances, swapping values for
wildcards, catching assertions, and deleting assertions are each one keystroke
away and each look locally reasonable (ImpossibleBench; Reward Hacking as a
Transmissible Strategy). This hook does not block; it names what it saw and asks
for the reason to be stated before continuing.

Reads the hook payload from stdin. Looks at the new content of the edited test
file (tool_input for Write/Edit) or, failing that, re-reads the file. Emits
additionalContext only when a pattern is present. Never crashes the tool call.
"""
import json
import os
import re
import sys

TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|spec|specs|Tests|.*Tests)(/|$)|"
    r"(_test\.|\.test\.|\.spec\.|^test_|Tests\.swift$|Test\.swift$|_tests\.rs$|/tests\.rs$)",
    re.I,
)

PATTERNS = [
    # skip / focus
    (r"@pytest\.mark\.skip\b|@unittest\.skip\b|pytest\.skip\(", "a skipped test (pytest/unittest skip)"),
    (r"\b(it|test|describe)\.(skip|only|todo)\(|\bx(it|test|describe)\(", "a skipped or focused test (.skip/.only/xit)"),
    (r"#\[ignore\]", "an ignored test (#[ignore])"),
    (r"\.disabled\(|XCTSkip|@Test\(\.disabled", "a disabled test (XCTSkip/.disabled)"),
    # weakening
    (r"\bpytest\.approx\([^)]*(rel|abs)\s*=\s*(0\.[1-9]|[1-9])", "a wide pytest.approx tolerance"),
    (r"\btoBeCloseTo\([^,)]+,\s*[0-2]\)", "a loose toBeCloseTo precision"),
    (r"\bexpect\.any(thing)?\(|\bmock\.ANY\b|\bANY\b", "a wildcard replacing a value (expect.any / mock.ANY)"),
    (r"\bassert\s+\w+\s+is\s+not\s+None\b|\btoBeDefined\(\)|\btoBeTruthy\(\)|XCTAssertNotNil\(|\.is_(ok|some)\(\)\s*\)\s*;?\s*$",
     "an existence-only assertion (not None / toBeDefined / is_ok)"),
    # catching assertions / conditional assertions
    (r"\bexcept\s+(AssertionError|Exception)\s*:\s*(pass|\.\.\.|continue)", "a caught assertion"),
    (r"\bcatch\s*\([^)]*\)\s*\{\s*\}", "an empty catch in a test"),
    (r"^\s*if\s+.*:\s*\n\s+assert\b|^\s*if\s*\(.*\)\s*\{\s*\n\s*expect\(", "an assertion behind a conditional"),
    # runner / equality tampering
    (r"__eq__\s*=|def\s+__eq__\(|\boverride\s+static\s+func\s*==", "an equality override introduced in test code"),
    (r"\bprocess\.exit\(\s*0\s*\)|\bsys\.exit\(\s*0\s*\)|\bexit\(0\)", "an explicit exit(0) in test code"),
    (r"--?(no-)?fail(-fast)?|--maxfail|testFailureIgnore|continueOnFailure|\btestPathIgnorePatterns\b|\bignore_glob\b",
     "a runner setting that hides failures"),
]

ASSERT_WORDS = re.compile(r"\b(assert|expect|XCTAssert|#expect|assert_eq!|assert!|should)\b")


def file_content(payload):
    _, ti, _ = _norm(payload)
    ti = ti or {}
    path = ti.get("file_path") or ti.get("path") or ti.get("filePath") or ""
    if "content" in ti and isinstance(ti["content"], str):
        return path, ti["content"], ti.get("old_string") or ""
    new = ti.get("new_string") or ti.get("new_str") or ""
    old = ti.get("old_string") or ti.get("old_str") or ""
    if new or old:
        return path, new, old
    try:
        if path and os.path.isfile(path) and os.path.getsize(path) < 2_000_000:
            with open(path, encoding="utf-8", errors="replace") as f:
                return path, f.read(), ""
    except Exception:
        pass
    return path, "", ""


def _norm(payload):
    """Accept Claude/Codex ({tool_name, tool_input, tool_response}) and Antigravity ({toolCall:{name,args}, toolResult}) shapes."""
    if not isinstance(payload, dict):
        return {}, {}, None
    tc = payload.get("toolCall") or {}
    name = payload.get("tool_name") or tc.get("name") or payload.get("toolName") or ""
    inp = payload.get("tool_input") or tc.get("args") or payload.get("toolInput") or {}
    resp = payload.get("tool_response", payload.get("toolResult", payload.get("toolOutput")))
    if isinstance(inp, dict) and "command" not in inp and "CommandLine" in inp:
        inp = dict(inp, command=inp["CommandLine"])
    if isinstance(inp, dict) and "file_path" not in inp:
        for k in ("TargetFile", "AbsolutePath", "path", "filePath"):
            if k in inp:
                inp = dict(inp, file_path=inp[k]); break
    if isinstance(inp, dict) and "content" not in inp and "CodeContent" in inp:
        inp = dict(inp, content=inp["CodeContent"])
    if isinstance(inp, dict) and "new_string" not in inp:
        for k in ("ReplacementContent", "new_str"):
            if k in inp:
                inp = dict(inp, new_string=inp[k]); break
    if isinstance(inp, dict) and "old_string" not in inp:
        for k in ("TargetContent", "old_str"):
            if k in inp:
                inp = dict(inp, old_string=inp[k]); break
    return name, inp, resp


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    try:
        name, _, _ = _norm(payload)
        if name not in ("Write", "Edit", "MultiEdit", "write", "edit", "str_replace", "create_file", "apply_patch",
                        "write_to_file", "replace_file_content", "multi_replace_file_content", "edit_file"):
            return 0
        path, new, old = file_content(payload)
        if not path or not TEST_PATH.search(path):
            return 0
        hits = []
        for pat, label in PATTERNS:
            if re.search(pat, new, re.M) and not re.search(pat, old, re.M):
                hits.append(label)
        # assertions removed by an Edit
        if old and ASSERT_WORDS.search(old):
            before = len(ASSERT_WORDS.findall(old)); after = len(ASSERT_WORDS.findall(new))
            if after < before:
                hits.append(f"{before - after} assertion(s) removed")
        if not hits:
            return 0
        seen = []
        for h in hits:
            if h not in seen:
                seen.append(h)
        msg = (
            f"The edit to {os.path.basename(path)} introduced: " + "; ".join(seen) + ". "
            "These are the moves that turn a suite green without fixing anything. If the contract intentionally changed, "
            "say so and list the edit and why. If not, treat the red test as correct until there is a concrete reason "
            "otherwise, state that reason before continuing, and prefer fixing the code. (behavioral-testing plugin)"
        )
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
