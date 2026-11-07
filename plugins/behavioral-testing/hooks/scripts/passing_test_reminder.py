#!/usr/bin/env python3
"""PostToolUse hook: when a test command just passed, ask the one question.

Research basis: a plain reminder at the moment a test passes ("consider whether
this check is sensitive to the behavior in question") accounted for about a
third of the improvement in bug-discriminating evidence in Xu & Wu (2026), with
no replay infrastructure. This hook delivers that reminder, and nothing else.

Reads the hook payload from stdin. Emits additionalContext only when the command
looks like a test run that passed. Never blocks. Never crashes the tool call.
"""
import json
import re
import sys

TEST_CMD = re.compile(
    r"(^|[\s;&|(])("
    r"pytest|python\s+-m\s+pytest|python\s+-m\s+unittest|"
    r"npx\s+(jest|vitest|mocha)|pnpm\s+(test|vitest|jest)|yarn\s+(test|vitest|jest)|npm\s+(test|run\s+test)|bun\s+test|"
    r"jest|vitest|mocha|node\s+--test|"
    r"cargo\s+(test|nextest)|"
    r"swift\s+test|xcodebuild\s+.*\btest\b|"
    r"go\s+test|mvn\s+test|gradle\s+test|./gradlew\s+test|"
    r"make\s+test|just\s+test"
    r")\b"
)

# Markers that a run reported success. Checked only when no failure marker is present.
PASS = [
    r"\b\d+ passed\b",                      # pytest
    r"\bTests:\s+\d+ passed",               # jest/vitest
    r"\bTest Files\s+\d+ passed",           # vitest
    r"\btest result: ok\b",                 # cargo
    r"\bExecuted \d+ tests?, with 0 failures\b",   # XCTest
    r"\bTest Suite .* passed\b",            # XCTest
    r"✔ Test run with \d+ tests? passed",   # Swift Testing
    r"^ok\b",                               # go, node --test
    r"\bBUILD SUCCESS\b",                   # maven
    r"\ball tests passed\b",
]
FAIL = [
    r"\b[1-9]\d* failed\b", r"\bFAILED\b", r"\bFAIL\b", r"\btest result: FAILED\b",
    r"\bwith [1-9]\d* failures?\b", r"\bTests:\s+[1-9]\d* failed", r"\berror\[E\d+\]",
    r"\bBUILD FAILURE\b", r"\bpanicked at\b", r"\bError: ", r"\bAssertionError\b",
]

REMINDER = (
    "A test command just passed. Before treating that as evidence, ask the one question the loop never asks: "
    "would this test have passed before your change? If yes, it is regression evidence at best and says nothing about "
    "the bug or feature. For a new or changed test: confirm it fails on the pre-change code on an assertion (not an import "
    "error), that its expected value came from the spec rather than from running the code, and that a different correct "
    "implementation would also pass it. If the only way to get here was to edit a test, say what you changed and why. "
    "(behavioral-testing plugin)"
)


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
        name, inp, resp = _norm(payload)
        if name not in ("Bash", "bash", "shell", "run_command", "execute_command", "run_terminal_cmd"):
            return 0
        cmd = str((inp or {}).get("command", ""))
        if not TEST_CMD.search(cmd):
            return 0
        text = ""
        if isinstance(resp, dict):
            text = " ".join(str(resp.get(k, "")) for k in ("stdout", "stderr", "output", "content"))
            code = resp.get("exit_code", resp.get("exitCode", resp.get("returncode")))
            if code not in (None, 0, "0"):
                return 0
        elif isinstance(resp, str):
            text = resp
        elif isinstance(resp, list):
            text = " ".join(str(x.get("text", x)) if isinstance(x, dict) else str(x) for x in resp)
        if any(re.search(p, text, re.M) for p in FAIL):
            return 0
        if not any(re.search(p, text, re.M) for p in PASS):
            return 0
        print(json.dumps({
            "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": REMINDER}
        }))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
