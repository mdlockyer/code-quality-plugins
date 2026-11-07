# Lenses

A lens is one question asked of one unit of code. Hunters run lenses one at a time and answer each with candidates or with `nothing applies: <reason>`. The point of a single question is attention: a reader asked "what's wrong with this file" skims; a reader asked "what happens when this write fails halfway through" traces.

Each lens below gives the question, what mature software does (the standard you compare against), where the bugs usually hide, and how to look. The "how to look" greps are starting points; the real work is reading what they point at and following the calls.

Candidates need a **trigger** (the input, state, or sequence that causes it), a **path** (file:line hops from trigger to impact), and an **impact**. A lens result that has none of those is a hunch, not a candidate.

---

## Core group (every rank-4/5 unit, all modes)

### L1 — Boundaries and malformed input

**Question:** For every value that enters this unit, what happens at the edges: empty, zero, negative, maximum, one-past-maximum, wrong type, wrong encoding, NaN, null, duplicate, unexpected order, absurdly large?

**Mature software:** rejects or normalizes at the boundary, once, and the rest of the code assumes the normalized form. Limits are explicit numbers with a reason.

**Where bugs hide:** length checks that use `<` where `<=` was meant; size checks after allocation; off-by-one at the last page, last chunk, last byte; `len()` of bytes vs characters; integer division and overflow at limits; checks on the client that are absent on the server; validation that runs on create but not on update; an optional field that is `None` on one path and `""` on another; a list that is empty on the first run.

**How to look:** every parameter and every deserialized field; every `[i]`, `[i+1]`, `len(...)-1`, range bound, slice, `substr`, offset arithmetic; every parse. Ask of each check "what is the smallest input that passes this check and still breaks the code below it?"

### L2 — Failure paths and partial state

**Question:** For every operation that can fail (I/O, network, DB, parse, allocation, external call), what is the state of the system immediately after the failure, and is it the state the rest of the code expects?

**Mature software:** every failure leaves the system in a defined state. Multi-step writes are transactional, idempotent, or compensated. Errors carry enough context to debug and are surfaced, not swallowed. Users see an actionable message, not a spinner.

**Where bugs hide:** `catch {}` and `except: pass`; `except Exception` that logs and continues with a half-initialized object; early returns that skip cleanup; a write to the DB followed by a write to the cache/queue/file with no handling for the second failing; retries that re-execute non-idempotent steps; timeouts that are missing or infinite; a lock or file handle not released on the error path; error messages that leak internals or say nothing; `finally` blocks that can themselves throw; partial batch processing with no record of which items succeeded.

**How to look:** grep for empty catch blocks, bare excepts, `.catch(() =>`, `unwrap()`/`expect()` on fallible calls, `log.error` followed by `continue`/`return nil`; list every external call and ask "and if this throws / returns an error / hangs / returns a 500 with a 200 body?"; every sequence of two or more writes.

### L3 — Intended versus implemented

**Question:** What does this unit claim to do (name, docstring, type signature, README, tests, comments, error messages, the UI copy that describes it) and where does the implementation diverge?

**Mature software:** names and docs match behavior because every mismatch has already caused a support ticket. Tests encode the contract, including the negative cases.

**Where bugs hide:** a function named `validate_*` that doesn't reject anything; a parameter documented as optional that the code dereferences; a default in the docstring that differs from the default in the signature; a `limit` that is actually ignored; `is_admin` checked where `is_owner` was intended; sort order described as newest-first and implemented as insertion order; a test that asserts the buggy behavior; a flag described in the README that the code never reads.

**How to look:** read the docstring, then the body, then the callers' expectations; diff the README/API docs against the actual routes and options; read the tests and ask what they *don't* assert; look for TODO/FIXME/HACK/XXX and whether the thing they describe ever got done.

### L4 — Concurrency, ordering, and time

**Question:** What happens when two of these run at once, or when events arrive in an order the author didn't picture, or when the clock, timezone, or locale is not the author's?

**Mature software:** shared state has an owner; check-then-act is atomic where it matters; idempotency keys exist for anything retried; all times are UTC internally and localized at the edge; durations use monotonic clocks.

**Where bugs hide:** read-modify-write on a counter, balance, or inventory without a transaction or atomic op; `if not exists: create` races; a cache populated from a stale read; background job and request handler touching the same row; signal/shutdown handlers racing with in-flight work; `datetime.now()` without tz; comparing naive and aware datetimes; day boundaries, DST, leap years, month-end arithmetic (`+1 month` from Jan 31); sorting with locale-dependent collation; `time.time()` used to measure elapsed time; unordered dict/set iteration treated as ordered; async code awaiting inside a loop that holds a lock.

**How to look:** every piece of shared mutable state and every path that touches it; every `now()`/`today()`/`Date()`; every "get then set"; every retry; the race detector or thread sanitizer if the language has one (`go test -race`, TSan); run the test suite twice in parallel.

---

## Trust group (units that cross a trust boundary: handlers, auth, permissions, anything touching user data)

### L5 — Who is allowed to do this

**Question:** For every operation reachable from this entry point, which principal may perform it on which object, and where exactly is that enforced?

**Mature software:** authorization is checked at the operation on the object (not just "is logged in"), consistently, in one place the handler cannot forget to call. Tenant scoping is in the query, not in a post-filter.

**Where bugs hide:** an endpoint that checks authentication but not ownership (IDOR); list endpoints that scope by tenant while get-by-id endpoints don't; bulk and export endpoints that skip the per-item check; admin checks on the UI route but not the API route; permission checks that read a role from the request body; tokens that never expire, aren't revoked on password change, or are compared with `==`; "internal" endpoints reachable from outside; a new route added without the middleware the others use.

**How to look:** build the matrix (operation × principal) from the routes and fill in where each cell is enforced; grep the `get_by_id`/`find(id)` calls and check which carry the tenant/owner filter; compare each route's middleware stack against its siblings'.

### L6 — Hostile input reaching a sink

**Question:** Can attacker-controlled bytes reach an interpreter (SQL, shell, template, regex, path, URL, deserializer, HTML, LDAP, log line that is later parsed) without being neutralized for *that* interpreter?

**Mature software:** uses parameterized queries, argument arrays not shell strings, allowlisted paths resolved and checked after normalization, safe deserializers, autoescaping templates, and treats stored data as untrusted when read back.

**Where bugs hide:** string-built SQL in the one place the ORM was inconvenient; `shell=True`; `os.path.join(base, user_input)` without checking the result stays under `base`; `pickle`/`yaml.load`/`unserialize` on anything from outside; `dangerouslySetInnerHTML`/`innerHTML`/`v-html`/`|safe`; regexes with nested quantifiers on user input; SSRF via a user-supplied URL fetched by the server; secrets in logs, URLs, error pages, or the repo.

**How to look:** list the sinks for the stack, then trace backward from each to its sources; `semgrep` with the stack's default ruleset; grep the obvious sink APIs and check what each receives.

---

## Persistence group (units that read or write durable state)

### L7 — Data lifecycle and integrity

**Question:** For every piece of persisted data, what guarantees its invariants over its whole lifetime: creation, update, concurrent update, migration, deletion, restore, and being read by code that didn't write it?

**Mature software:** invariants are enforced by the database (constraints, foreign keys, unique indexes), not only by application code; migrations are reversible and tested against real-shaped data; deletes cascade or refuse deliberately; soft-deleted rows are excluded everywhere.

**Where bugs hide:** uniqueness enforced in code but not the schema (so the race in L4 creates duplicates); a nullable column the code treats as non-null; enum values added in code but not in the DB constraint or in the old rows; migrations that lock a big table or run data backfills in the same transaction; a `deleted_at` filter missing on one query; ORM lazy loading causing N+1 at scale; a JSON column whose shape has drifted across versions with no version field; money as float; IDs that are predictable where they shouldn't be; a cascade delete that removes more than intended.

**How to look:** compare every model/schema definition against the code that writes it; read every migration; list every query on a soft-deletable table; find every float used for currency or quantity.

### L8 — Resources, limits, and scale

**Question:** What grows without bound, what is never released, and what is linear in something an outside party controls?

**Mature software:** every list from outside is bounded; every loop over user data is paginated or streamed; connections, files, and subprocesses are released in `finally`/`with`/`defer`; memory and queue depth have ceilings; hot paths have been measured.

**Where bugs hide:** `SELECT *` with no `LIMIT` on a user-filterable query; loading a whole file or response into memory; N+1 queries behind an innocent loop; unbounded caches and in-memory maps keyed by user input; connection pools exhausted by a leaked connection on an error path; a regex on untrusted input with catastrophic backtracking; recursion on user-shaped data; retries without backoff that amplify an outage; a per-request thread or subprocess; missing timeouts on outbound calls so a slow dependency stalls the whole service.

**How to look:** every allocation, collection, or query whose size depends on input; every acquire without a matching release on all paths; every outbound call's timeout; profile or at least reason about the largest realistic tenant.

---

## Operations group (units involved in startup, config, deploy, jobs, integrations)

### L9 — Configuration and environment

**Question:** What differs between the developer's machine, CI, staging, and production, and which of those differences does the code silently depend on?

**Mature software:** configuration is explicit, validated at startup (fail fast on a missing or malformed setting), and the same code path runs in every environment with only values changing. Defaults are safe for production, not convenient for development.

**Where bugs hide:** `DEBUG=True` defaults; a feature flag read from an env var that is unset in prod and therefore falsy; secrets with development fallbacks (`os.getenv("KEY", "dev-key")`); CORS `*`; a hardcoded `localhost` or port; a dependency on working directory; a config value parsed as string where an int was expected (`"false"` is truthy); timezone of the host; a path with the developer's username in it; a different serializer/version/database engine in tests than in production; migrations that run on import.

**How to look:** every `getenv`/config read and its default; every literal hostname, port, path, or credential; the Dockerfile and CI config against the README's run instructions; the test configuration against production configuration.

### L10 — Startup, shutdown, jobs, and recovery

**Question:** What happens when the process starts with the world in an unexpected state, is killed mid-work, or is restarted twice?

**Mature software:** startup validates its dependencies and fails loudly; shutdown drains in-flight work; jobs are idempotent and resumable; a crash never corrupts state because every durable write is atomic; health checks reflect real readiness.

**Where bugs hide:** a scheduled job that assumes the previous run finished; two instances running the same cron job; a health endpoint that returns 200 while the DB is unreachable; SIGTERM ignored so the orchestrator SIGKILLs mid-transaction; a temp file written in place instead of write-then-rename; a queue consumer that acks before processing; state in process memory that is lost on restart and never rebuilt; initialization order that depends on import order; a lock file left behind after a crash.

**How to look:** read `main`/startup, the signal handling, every scheduler and consumer; ask of each job "if this is killed after line N, what happens on the next run?"

### L11 — Dependencies and integrations

**Question:** For every external system and library, what does the code assume about its behavior, version, and availability that isn't guaranteed?

**Mature software:** pins versions, handles the documented error cases of each API, treats every external response as untrusted, and degrades deliberately when a dependency is down.

**Where bugs hide:** assuming an external call succeeded because it didn't throw (HTTP 200 with an error body, partial writes); ignoring pagination in an API response; a webhook handler without signature verification or replay protection; a library upgrade that changed a default (strict mode, timezone handling, escaping); an unpinned dependency; deprecated calls; a client SDK that retries internally while the code retries again; an integration whose failure cascades into a user-visible outage with no circuit breaker.

**How to look:** lockfiles and version ranges; every call to an external client and what it does with the response; vulnerability and deprecation scanners for the stack.

### L12 — Observability and operability

**Question:** When this unit misbehaves in production, how will anyone know, and will the information they get be enough to fix it?

**Mature software:** logs the inputs that matter (not the secrets), with correlation IDs; errors include the identifiers needed to find the affected records; metrics exist for the things that have paged someone before; a human can turn off a risky feature without a deploy.

**Where bugs hide:** errors logged without the request/job/user ID; a catch block that logs `str(e)` and loses the traceback; log lines at INFO in a loop; PII or tokens in logs; no way to tell which version is running; an alert condition that can't be observed from outside; a feature with no kill switch.

**How to look:** read the catch blocks and the logging calls in the hot paths; ask of each failure mode in L2 "which log line or metric would reveal this?"

---

## Interface group (units that expose an API, CLI, or UI to others)

### L13 — Contract and compatibility

**Question:** What does a client of this unit depend on, and what in the code can change that under them?

**Mature software:** APIs are versioned or additive-only; field names, types, enum values, ordering, and error shapes are stable; removed things go through deprecation; the CLI's exit codes and output formats are documented and tested.

**Where bugs hide:** a response field that is sometimes a string and sometimes a number; `null` vs missing key; an enum that gained a value the clients don't handle; a sort order that changed when the query changed; error responses with different shapes on different paths; an API that returns 200 on failure; a CLI that prints errors to stdout; pagination tokens that break when the underlying order changes; breaking changes in a minor version.

**How to look:** compare the API schema/docs with the actual serialization; list every distinct error response; check what happens to an old client when a new field or value appears.

### L14 — The user's experience of failure

**Question:** When something goes wrong, what does the person on the other end actually see, and can they do anything about it?

**Mature software:** every failure has a message that says what happened and what to do; forms keep the user's input; retries are safe to click twice; long operations show progress and can be cancelled; the UI never lies about state (a success toast after a failed save).

**Where bugs hide:** a generic "Something went wrong"; a success message rendered before the request completes; a disabled button that never re-enables; a form that clears on validation error; a double-submit creating two records; a loading state with no timeout; a confirmation dialog on the wrong action; a 500 where a 400 with a reason was warranted.

**How to look:** trace each user-initiated action from click to response to render, including the failure branches; look at what the frontend does with each error shape the backend can return.

---

## Variant hunting (standing instruction for every lens)

When a lens produces a candidate, the same mistake has usually been made elsewhere by the same author or copied from the same source. Before finishing the lens, grep the codebase for the pattern (the same API, the same shape of check, the same helper used the same way) and list every other location. Report the class with all locations under one finding. Mature software fixes classes.

## Maturity signals (use during recon to weight lenses)

These are quick greps that indicate where years-of-refinement work hasn't happened yet. They are not findings by themselves; they tell you where to look harder.

- Suppressions: `# noqa`, `# type: ignore`, `@ts-ignore`, `@ts-expect-error`, `eslint-disable`, `#nosec`, `// nolint`, `@SuppressWarnings`, `unsafe`
- Skipped or weakened tests: `skip`, `xit`, `xtest`, `@pytest.mark.skip`, `t.Skip`, `only`, `.todo`
- Debt markers: `TODO`, `FIXME`, `HACK`, `XXX`, `WORKAROUND`, `temporary`
- Swallowed failures: empty catch blocks, bare `except`, `catch (e) {}` , `.catch(() => {})`, `_ = err`
- Panics on fallible calls: `unwrap()`, `expect(`, `!` non-null assertions, `as any`
- Hardcoded environment: `localhost`, `127.0.0.1`, `/home/`, `/Users/`, `C:\\`, `password`, `secret`, `token` literals
- Time handling: `now()`, `today()`, `Date()`, `time.time()`, `sleep(`
- Shell and eval: `eval(`, `exec(`, `shell=True`, `system(`, `Function(`, `new Function`
- Git: files with the highest count of fix/bug/revert commits; files with high churn and low test coverage
