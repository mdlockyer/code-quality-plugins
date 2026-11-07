# Evidence behind the rules (as of November 7, 2026)

Use this when a user asks "why so strict?" or when deciding how hard to push on a rule. Each entry: the rule, the finding, the source and date.

Read the numbers with care. Most 2026 sources are arXiv preprints; peer-reviewed ones are marked. The figures were collected from the papers' abstracts and from secondary write-ups, not independently re-derived, and several come from a single study with a specific benchmark and model set. Treat them as "the direction and rough size of the effect," quote the source if you quote the number, and do not present any of them to a user as settled fact. The guidance in SKILL.md stands on the *direction* of these findings; they would survive the numbers being off by half.

## Rule → evidence map

**Expected values should come from somewhere other than the implementation.**
- Tests generated from the task description alone detected ~25% of injected faults; tests generated with the (possibly faulty) implementation visible detected ~14%. Exposing code reduced fault detection by 13.2% on average; an agentic same-session workflow was 11.7% worse than an independent test-first one. Coverage was 95–99% in all conditions and explained nothing — assertion quality did. Chain-of-thought and self-verification prompting did not help. — Konstantinou, Tambon & Papadakis, *On the risk of coding before testing*, arXiv 2607.05139, July 2026.
- Tests generated from buggy code are "misguided" (pass on the bug, fail on the fix) 3.84% of the time vs 0.46% from fixed code; effective tests 2.98% vs 8.51%. Replacing the code in the prompt with a specification docstring cut misguided tests and raised effective tests to 4.50%; giving docstring *plus* code was worse than docstring alone. Stronger models were *more* misguidable (r = 0.90). — Zhao, Zhou & Cohen, *Evaluating and Mitigating the Misguidance Effect of Buggy Code in LLM-Generated Unit Tests*, ISSTA 2026 (peer-reviewed), arXiv 2607.22883.
- 8–17% of LLM-generated regression tests were *fault-enforcing* (lock in an existing bug) vs only 2.4–4.8% fault-revealing; 83–92% of enforced faults remained enforced across later commits. — Charoosaei, Richter & Papadakis, *On the Risks of using LLM-Generated Tests for Regression Testing*, arXiv 2610.11835, Oct 8, 2026.
- Tests for incorrect code had a 47% worse bug-detection rate; adding a natural-language description improved bug detection by 34%. — Huang, Zhang, Harman et al., *Measuring the Influence of Incorrect Code on Test Generation*, arXiv 2409.09464 (2024–25).

**A passing test is evidence only if it fails on the code before the change; keep reproduction tests spec-aligned, not patch-specific.**
- Replaying every validation command repair agents ran on three code states (buggy original B, the agent's candidate S, the developer's gold fix G), across 3,730 events in 643 runs on 110 SWE-bench Verified / SWE-rebench tasks: 46.0% of positive comparable events were regression-only or misleading (they also passed on B); 23.8% of baseline runs closed with *no* bug-discriminating evidence at all. Of the tests that did fail on B and pass on S, 26.9% also failed on G — pinned to the agent's own patch. Feeding the B-replay outcome back to the agent cut evidence-inadequate closure by 7.8 points vs. an attention-matched reminder; the plain reminder ("consider whether this check is sensitive to the reported behavior") alone accounted for about a third of the total improvement and recurred on a second model. Single provider, Python benchmarks, effects below the authors' own 10-point threshold of interest. — Xu & Wu, *Validation Evidence in LLM Repair Agents: How Much of What Passes Actually Tests the Bug?*, arXiv 2607.28871, July 2026.
- Agents on SWE-bench Verified write tests often, but most mid-task "validation" is print-statement exploration rather than assertion-bearing tests, test-writing frequency is similar in successful and failed runs, and prompting for more or fewer tests does not change outcomes. — Z. Chen et al., *Rethinking the Value of Agent-Generated Tests for LLM-Based Software Engineering Agents*, arXiv 2602.07900, Feb 2026.
- A fail-to-pass test can be produced by first generating a test that *passes* on the buggy code for the issue's scenario, then inverting its assertion. — Khatib, Mathews & Nagappan, *AssertFlip: Reproducing Bugs via Inversion of LLM-Generated Passing Tests*, ICSE 2026 (peer-reviewed), arXiv 2507.17542.
- Benchmark regression suites are often too weak to separate correct from incorrect patches; mutation-guided diagnosis exposes the gap. — Sun et al., *SWE-Mutation: Can LLMs Generate Reliable Test Suites in Software Engineering?*, Findings of ACL 2026 (peer-reviewed), arXiv 2605.22175.

**Validate what you ship as a user would; the visible check is not the spec.**
- In a controlled code-as-spec study (two production Copilot CLI agents, a hidden 222-test Playwright oracle, 18 runs, three oracle-availability conditions), agents without the oracle under-built the library honestly and the scores showed it; with the oracle in the loop they drove scores to near-perfect by inlining the tested behavior into a throwaway demo while the requested reusable library shipped dead or absent. The oracle was honest and source-hidden, so this is not leakage or cheating; the authors call the disposition "building to the test" and the missing trait "validation self-awareness." Every verdict was re-checked with a no-op ablation to confirm the check could fail. Small N; two agents; one task family. — Ma, Kereopa-Yorke & Schultz (Microsoft), *Building to the Test: Coding Agents Deliver What You Check, Not What You Requested*, arXiv 2606.28430, June 2026.

**Oracle ladder; no assertion-free, existence-only, boolean-only, mock-only or snapshot-only tests.**
- Across 86,156 test-file patches from 33,596 agent PRs (Codex, Copilot, Devin, Cursor, Claude Code), 80.2% had weak or no explicit oracle; only 11.3% had value assertions and 5.7% multi-signal strong oracles. Strong oracles were associated with higher merge likelihood (OR 1.28). The W1–W5 / S1–S3 taxonomy in `oracle-ladder.md` is theirs. — Banik, Chowdhury & Shamim, *All Smoke, No Alarm: Oracle Signals in Agent-Authored Test Code*, arXiv 2606.18168, June 2026.
- Mature suites show gaps of up to 51% between code that is executed and code whose results are actually checked ("checked coverage"), cited in the same paper.

**Get evidence the test can fail (repro before fix, revert-check, deliberate mutant, mutation on changed code).**
- A controlled experiment instructing an agent (Claude Sonnet 4.6) to do TDD found no mutation-score improvement, 3–8.5× token cost, and agents that "skipped or faked the red step, or implemented ahead of the test"; some tests checked the implementation's output against itself. Conclusion: a red test proves the agent saw a failure, not that it failed for the right reason; prefer outcome checks (mutation testing, static analysis). Small sample; LLM-judged. — Birgitta Böckeler, *TDD inside the agent loop – theater or actual value?*, martinfowler.com, Aug 10, 2026.
- "Reddening": after coding, temporarily revert production code while keeping the new tests, expect red, restore, expect green; compile failure is a weak red. — Paul Hammant, *Red-Green-Refactor Moves Into the Harness*, Oct 14, 2026 (rev. Nov 4, 2026).
- TDD prompting alone *increased* regressions for smaller models (6.08% → 9.94%). — *TDAD: Test-Driven Agentic Development*, arXiv 2603.17973, 2026.
- Mutation testing moved to **Adopt** in Thoughtworks Technology Radar Vol. 35 (Nov 4, 2026) specifically because AI-generated tests make line coverage easy to inflate; recommends incremental runs on recently changed code.
- Meta's mutation-guided test generation (ACH): 49% of the useful tests it produced would have been discarded under a line-coverage criterion; 73% acceptance by engineers. — Foster, Harman et al., *Mutation-Guided LLM-based Test Generation at Meta*, FSE 2025 Companion (peer-reviewed); Meta Engineering blog, Feb and Sept 2025.
- Coverage and mutation scores track real fault detection in regression settings (code assumed correct) but "no longer serve as reliable indicators" when the goal is finding bugs already in the code. — Zhao, Zhou & Cohen, *Do Coverage and Mutation Scores of LLM-Generated Test Suites Correlate with Their Effectiveness?*, ISSTA 2026 (peer-reviewed), arXiv 2607.22880.
- Classic result: coverage is not strongly correlated with effectiveness once suite size is controlled. — Inozemtseva & Holmes, ICSE 2014; Papadakis et al., ICSE 2018.

**Don't change a test's meaning silently; say what you think is wrong and let the user decide.**
- On benchmark variants where tests contradict the spec, agents cheated by modifying tests, special-casing inputs, and overloading operators; one model's cheating on the conflicting variant fell from 93% to 1% when told "STOP if tests are flawed, do NOT carve out the code." Agents with test access "may delete failing tests rather than fix the underlying bug." — Zhong, Raghunathan & Carlini, *ImpossibleBench*, arXiv 2510.20270, Oct 2025.
- Observed hacks in multi-agent coding: always-true `__eq__`, conftest hooks that rewrite pytest reports, process exit before assertions; strategies spread between agents. — *Reward Hacking as a Transmissible Strategy in Multi-Agent Coding Systems*, arXiv 2610.12822, Oct 2026.
- Agents memorize visible validation tests in lookup tables or implement features in isolation; the gap between visible and held-out tests grows with task complexity. — *SpecBench*, arXiv 2605.21384, May 2026.
- Kent Beck on agents: they delete or disable tests and fake implementations with hardcoded lookup tables; he wants an immutable "this test is correct" marker. — Pragmatic Engineer interview, June 2025; *Augmented Coding: Beyond the Vibes*.

**Test doubles: real → fake → stub → mock; never mock the unit under test; contract-test fakes.**
- Agent commits add mocks far more often than non-agent commits (36% vs 26%); authors recommend putting mocking guidance in agent configuration. — Hora & Robbes, *Are Coding Agents Generating Over-Mocked Tests?*, MSR 2026 (peer-reviewed), arXiv 2602.00409.
- Agent-generated mocks are "executable but unfaithful": execution-feedback loops fix runtime errors but not behavioral fidelity or interaction-fault detection; passing tests mask behavioral deviations. — Ning et al., *Executable but Unfaithful: Mock Object, Stub, and Assertion Generation by LLMs and Coding Agents*, arXiv 2610.14629, Oct 10, 2026.
- Google's standing guidance: prefer real implementations, then fakes; test state not interactions; don't mock types you don't own; mock overuse yields tests that pass while code is broken. — *Software Engineering at Google* ch. 12–13; Testing on the Toilet 2013, 2020, Feb 2024.

**Property-based tests when the spec offers an invariant.**
- An agent writing Hypothesis properties across 100 Python packages produced 984 bug reports; in a 50-report sample 56% were valid bugs; patches merged into NumPy and cloud SDKs. — Maaz et al. (Anthropic / Northeastern / Hypothesis maintainer), *Agentic Property-Based Testing*, arXiv 2510.09907, NeurIPS 2025 DL4Code workshop.
- Across compilers, databases, DL libraries and LLM serving engines: 180 reports, 65 maintainer-confirmed, 23 fixed; most were wrong-result bugs that only an oracle detects; domain fuzzers still win where observability is low. — Naziri, Qin, Patel & d'Amorim, arXiv 2610.34487, Oct 25, 2026.
- Constraining LLMs to fill property templates cut intent misalignments from 22 to 1. — arXiv 2607.09072, 2026.

**Determinism; sort unordered collections; don't copy flaky patterns from context.**
- LLM-generated tests were slightly flakier than existing tests; when a flaky assertion was present in the prompt context it reappeared in 69% of GPT-4o's SAP HANA tests; unordered collections were the top root cause (63% of flaky tests). Authors: fix flaky tests *before* applying LLM generation. — Berndt et al., ICSE SEIP 2026 (peer-reviewed), arXiv 2601.08998.
- Async waits (45%), concurrency (20%) and order dependency (12%) dominate flaky-test fixes. — Luo et al., FSE 2014. Concurrency remains the top root cause in SAP HANA issue reports (FTW 2026).

**Fewer, stronger tests; don't pad for coverage.**
- Prompting for more tests (CoT, chain-of-verification) raised count without raising detection. — Konstantinou et al., 2026.
- In 114,134 merged Java PRs, agent-supported PRs added tests more often, but in test-only PRs their tests covered less of the exercised code; the relationship with quality "remains uncertain." — Milanese et al., arXiv 2610.35297, Oct 26, 2026.
- Thoughtworks Radar Vol. 34 (Apr 2026): rising rework rate is an early warning of unchecked AI-assisted development. DORA 2025 (Sept 2025): AI adoption associated with higher throughput and higher delivery instability; AI amplifies existing practices.

**Name the behavior; one behavior per test; literals carry their derivation.**
- Across 20,505 LLM-generated Java suites (four models), 972 TestBench cases, 14,469 EvoSuite tests and 779,585 human-written tests, LLM-generated tests consistently show Assertion Roulette, Magic Number Test and Empty Test, with prevalence shaped by prompting strategy, context length and model scale; smell profiles overlap with human-written tests enough to suggest inheritance from training data. Earlier work found smelly tests are more change- and defect-prone, with Indirect Testing, Eager Test and Assertion Roulette the most significant. — Ouédraogo et al., *On the Diffusion of Test Smells in LLM-Generated Unit Tests*, arXiv 2410.10628 (v3, 2026); Spadini et al. on test-smell harm.

**LLM-as-judge is not a correctness oracle.**
- Position and self-preference bias and inconsistent test-retest reliability on code judging. — *Bias in the Loop*, arXiv 2604.16790, 2026; CodeJudgeBench, ACL 2026; systematic review in IEEE Access 2026 (arXiv 2607.05031).

## Folklore the evidence does not support

- Coverage percentage targets (gamed by superficial tests; uncorrelated with detection in 2026 studies).
- "The agent did TDD, so the tests are good" (faked red steps; no mutation gain).
- "Execution feedback makes tests correct" (it makes them *run*).
- "LLM regression tests are a safe default for legacy code" (they enforce bugs; label as characterization).
- One-assert-per-test absolutism (the principle is one *behavior* per test).
- Pyramid-vs-trophy shape dogma (no 2025–26 evidence settles it; choose by risk and feedback cost).
- Mutation score as a number to maximize (equivalent mutants; context-dependent validity; it is a signal, not a target).
- "The test passes, so the bug is fixed" (46% of agents' passing checks also pass on the bug; ask whether it failed before the change).
- "The hidden test suite is green, so the deliverable is done" (agents satisfy honest oracles by building to the test; audit the artifact, not the score).

## Where sources disagree

- Beck, Willison and Anthropic's Claude Code guidance recommend test-first; Böckeler's experiment and TDAD find TDD *instructions alone* don't improve outcomes. The reconciliation used in this skill: the active ingredient is oracle independence plus mechanical verification of failure, and test-first is one way to get it.
- Milanese et al. (Oct 2026) find agent-vs-human test quality "uncertain" in merged Java PRs; Banik et al. find weak oracles dominant but don't compare to humans. Merged-PR samples are reviewer-filtered, so both can be true.
