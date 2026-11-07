---
tags: [production-code-audit]
max_turns: 250
timeout_seconds: 5400
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash, Task]
---

We're launching the billing and checkout service to paying customers next month. Go deep: I want every bug and edge case you can find in anything that touches money, auth, or the database, with proof. Then fix the ones I approve.
