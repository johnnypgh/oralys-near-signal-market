
## Stage 01: contract-v2 and sandbox tests

Implemented only the Stage 01 files. All fixtures are SAMPLE DATA. NEAR is Oralys's home chain. No installs, live chain calls, signing with real keys, or deployment performed.

Initial syntax-check attempt used TypeScript transpileModule with ScriptTarget.ES2022 and ModuleKind.ESNext through node --input-type=module. It exited 1 with this output:

```text
file:///Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/[eval1]:6
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
                                             ^

TypeError: Cannot read properties of undefined (reading 'ES2022')
    at file:///Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/[eval1]:6:46
    at ModuleJob.run (node:internal/modules/esm/module_job:430:25)
    at process.processTicksAndRejections (node:internal/process/task_queues:104:5)
    at async onImport.tracePromise.__proto__ (node:internal/modules/esm/loader:262:26)
    at async ModuleLoader.executeModuleJob (node:internal/modules/esm/loader:259:20)
    at async asyncRunEntryPointWithESMLoader (node:internal/modules/run_main:101:5)

Node.js v25.6.1
```

### `cd contract-v2 && cargo test`

Executed offline with npm_config_offline=true, npm_config_yes=false, CI=1.

```text
/bin/sh: cargo: command not found
```
Exit: 127

### `npm run build:contract:v2 && npm run test:sandbox:v2`

Executed offline with npm_config_offline=true, npm_config_yes=false, CI=1.

```text

> oralys-near-signal-market@0.1.0 build:contract:v2
> cd contract-v2 && cargo near build non-reproducible-wasm

sh: cargo: command not found
```
Exit: 127

### `npm run test:sandbox:v2`

Executed offline with npm_config_offline=true, npm_config_yes=false, CI=1.

```text

> oralys-near-signal-market@0.1.0 test:sandbox:v2
> tsx --test integration-tests/market-v2.test.ts

node:fs:555
  return binding.open(
                 ^

Error: ENOENT: no such file or directory, open '/Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/contract-v2/target/near/oralys_signal_market_v2.wasm'
    at Object.openSync (node:fs:555:18)
    at readFileSync (node:fs:439:35)
    at <anonymous> (/Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/integration-tests/market-v2.test.ts:11:14)
    at ModuleJob.run (node:internal/modules/esm/module_job:430:25)
    at async onImport.tracePromise.__proto__ (node:internal/modules/esm/loader:655:26)
    at async asyncRunEntryPointWithESMLoader (node:internal/modules/run_main:101:5) {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: '/Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/contract-v2/target/near/oralys_signal_market_v2.wasm'
}

Node.js v25.6.1
✖ integration-tests/market-v2.test.ts (336.943958ms)
ℹ tests 1
ℹ suites 0
ℹ pass 0
ℹ fail 1
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 342.233167

✖ failing tests:

test at integration-tests/market-v2.test.ts:1:1
✖ integration-tests/market-v2.test.ts (336.943958ms)
  'test failed'
```
Exit: 1

### `npx tsc --noEmit`

Executed offline with npm_config_offline=true, npm_config_yes=false, CI=1.

```text
integration-tests/market-v2.test.ts(40,66): error TS2769: No overload matches this call.
  The last overload gave the following error.
    Argument of type 'string | undefined' is not assignable to parameter of type 'string'.
      Type 'undefined' is not assignable to type 'string'.
integration-tests/market-v2.test.ts(43,42): error TS2769: No overload matches this call.
  The last overload gave the following error.
    Argument of type 'string | undefined' is not assignable to parameter of type 'string'.
      Type 'undefined' is not assignable to type 'string'.
```
Exit: 1

### `npx expo lint`

Executed offline with npm_config_offline=true, npm_config_yes=false, CI=1.

```text

ESLint has been configured 🎉


/Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/agent/src/env.ts
  17:13  warning  Array type using 'Array<T>' is forbidden. Use 'T[]' instead  @typescript-eslint/array-type

/Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/agent/src/near.ts
  13:11  warning  Array type using 'Array<T>' is forbidden. Use 'T[]' instead  @typescript-eslint/array-type

/Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/scripts/demo.ts
  21:17  warning  Array type using 'Array<T>' is forbidden. Use 'T[]' instead  @typescript-eslint/array-type

✖ 3 problems (0 errors, 3 warnings)
  0 errors and 3 warnings potentially fixable with the `--fix` option.

```
Exit: 0

### V1 regression command

`cd contract && cargo test` was not run, as directed. The v2 cargo attempt above reports `/bin/sh: cargo: command not found`. V1 sources were not changed. No Rust or WASM acceptance check passed.

### TypeScript fixes and final checks

Fixed both assertion-message type errors by providing fallback strings. The installed TypeScript package does not expose the compiler API used in the first syntax-check attempt. The sandbox command successfully loaded the TypeScript test before failing on the missing WASM.

`npx tsc --noEmit` (offline, after fixes):

```text
(no output)
```
Exit: 0

`npx expo lint` (offline, after fixes):

```text

/Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/agent/src/env.ts
  17:13  warning  Array type using 'Array<T>' is forbidden. Use 'T[]' instead  @typescript-eslint/array-type

/Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/agent/src/near.ts
  13:11  warning  Array type using 'Array<T>' is forbidden. Use 'T[]' instead  @typescript-eslint/array-type

/Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/scripts/demo.ts
  21:17  warning  Array type using 'Array<T>' is forbidden. Use 'T[]' instead  @typescript-eslint/array-type

✖ 3 problems (0 errors, 3 warnings)
  0 errors and 3 warnings potentially fixable with the `--fix` option.

```
Exit: 0

Expo lint automatically added a lint script and created .expo/. Both generated changes were removed after the checks to preserve Stage 01 scope. Lint reported only three warnings in unchanged v1 files. No existing scripts were changed.

Rust test cases declared: 66 (source count, not executed). Every section 3 panic is covered, including the defensive budget guard by a unit-only state setup. Extra cases cover v1 signatures, signature field tampering, inclusive time bounds, payout order, the 200-payout cap, owner rotation, and refund amounts.

Status: Stage 01 implementation complete but Rust compilation, Rust tests, WASM build, and sandbox execution remain unverified. A Rust-equipped offline review environment with dependencies and a local sandbox is required. V1 regression tests remain unrun. Stage 02 and Stage 03 were not started. No bundle or patch created.

### Final source review

Static checks only, not Rust execution:

```text
Dash scan: no em or en dashes in the seven Stage 01 files.
package.json: only the three authorized scripts were added.
Cargo dependencies, release profile, and toolchain match v1.
All 24 distinct section 3 panic strings appear unchanged in contract and tests.
git diff --check: exit 0, no output.
```


## Stage 02: v2 query, matcher, excerpts and oracle

Implemented only the seven Stage 02 modules, four test files and the test:agent:v2 package script. All fixture data is SAMPLE DATA. NEAR is Oralys's home chain.

The oracle tests generate throwaway keys in memory. No key files were read or written. loadOrCreate is implemented for later owner use but was not invoked. No network, install, chain, deploy or signing with real keys occurred. Stage 01 and its integration test were not changed; that test still signs independently, so the conditional sandbox rerun does not apply. Stage 03, bundle and patch were not started.

Initial check: npm run test:agent:v2 failed because of an invalid escaped quote in a Unicode regular expression. Exact diagnostic and summary excerpts:

```text
SyntaxError: Invalid regular expression: /[\s()\"]/u: Invalid escape
Node.js v25.6.1
ℹ tests 6
ℹ suites 0
ℹ pass 3
ℹ fail 3
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 201.581208
```

The regex escape was removed. The next test run passed all 45 tests. The initial npx --no-install tsc --noEmit produced no output. Final acceptance output below is captured directly, including exit codes. The installed runtime reports Node v25.6.1, not the Node 24 in the task description.

### npm run test:agent:v2

```text

> oralys-near-signal-market@0.1.0 test:agent:v2
> tsx --test agent/src/v2/*.test.ts

✔ fixture matches exactly at anchor, five minutes later and with a 7200 second window (1.957792ms)
✔ fixture separate anchors do not overlap and excerpts carry correct metadata and hashes (0.143208ms)
✔ selection excludes paid excerpts, sorts ties by id and honors maxCount (0.223166ms)
✔ time and quality boundaries are inclusive and future and old segments are excluded (0.075417ms)
✔ over 400 characters drops context first (0.068667ms)
✔ overlong anchor cuts at a word boundary and keeps a surviving match (0.075292ms)
✔ cut that loses match produces no excerpt, including AND group loss (0.074ms)
✔ 400 character sentence is not cut (0.046708ms)
✔ anchor must contain a term of a satisfied group and AND cannot span separate excerpts (0.14325ms)
✔ sha256 known vector (0.073916ms)
✔ replay shifts timestamps without changing source segments (0.201417ms)
✔ feed rejects missing labels, unsafe ids and invalid dates without writing fixture files (2.807542ms)
✔ NFKC and Unicode letter and digit runs (1.377708ms)
✔ whole token matching excludes prefixes (0.378875ms)
✔ phrase tokens must be contiguous (0.082125ms)
✔ AND groups and returned OR group indexes (0.10375ms)
✔ sentence split preserves punctuation and ignores empty edges (0.082375ms)
✔ exact v2 signing message binds all fields in order (0.493209ms)
✔ throwaway seed only, hex signature verifies with node:crypto and rejects changed fields (2.626917ms)
✔ malformed seeds are rejected without exposing seed contents (0.168416ms)
✔ QueryError: query is empty ("") (0.898042ms)
✔ QueryError: query is empty ("  ") (0.048042ms)
✔ QueryError: query is longer than 256 characters ("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa") (0.036458ms)
✔ QueryError: expected a term ("AND a") (0.307666ms)
✔ QueryError: expected a term ("a OR") (0.070041ms)
✔ QueryError: expected a term ("a AND OR b") (0.041459ms)
✔ QueryError: missing closing parenthesis ("(a") (0.041542ms)
✔ QueryError: unexpected ) ("a)") (0.071792ms)
✔ QueryError: unexpected ) (")") (0.046458ms)
✔ QueryError: missing AND or OR between terms ("a b") (0.08425ms)
✔ QueryError: missing AND or OR between terms ("a(b)") (0.045792ms)
✔ QueryError: missing AND or OR between terms ("(a b)") (0.045083ms)
✔ QueryError: NOT is not supported ("NOT a") (0.032375ms)
✔ QueryError: NOT is not supported ("a and not b") (0.026458ms)
✔ QueryError: wildcards are not supported ("a*") (0.024209ms)
✔ QueryError: wildcards are not supported ("\"a?\"") (0.023542ms)
✔ QueryError: use OR between terms, not a comma ("a,b") (0.020709ms)
✔ QueryError: unterminated quote ("\"abc") (0.028667ms)
✔ QueryError: empty term ("\"   \"") (0.027375ms)
✔ QueryError: empty term ("---") (0.020791ms)
✔ QueryError: more than 16 groups ("a0 OR a1 OR a2 OR a3 OR a4 OR a5 OR a6 OR a7 OR a8 OR a9 OR a10 OR a11 OR a12 OR a13 OR a14 OR a15 OR a16") (0.147ms)
✔ QueryError: more than 16 groups ("(a OR b OR c OR d OR e) AND (f OR g OR h OR i)") (0.091083ms)
✔ QueryError: more than 8 terms ("a0 AND a1 AND a2 AND a3 AND a4 AND a5 AND a6 AND a7 AND a8") (0.06375ms)
✔ canonical format, operator precedence, phrases and round trips (0.242291ms)
✔ limits allow exactly 256 characters, 16 groups and 8 distinct terms (0.230375ms)
ℹ tests 45
ℹ suites 0
ℹ pass 45
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 138.712458
```

Exit code: 0.

### npx tsc --noEmit

```text
```

Exit code: 0.
No stdout or stderr.

### Standing workspace lint check

Attempted `npx --no-install expo lint` with offline mode and CI enabled, without allowing installation. This Stage 02 repository is a NEAR agent project and does not declare Expo.

```text

ESLint has been configured 🎉


/Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/agent/src/env.ts
  17:13  warning  Array type using 'Array<T>' is forbidden. Use 'T[]' instead  @typescript-eslint/array-type

/Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/agent/src/near.ts
  13:11  warning  Array type using 'Array<T>' is forbidden. Use 'T[]' instead  @typescript-eslint/array-type

/Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/scripts/demo.ts
  21:17  warning  Array type using 'Array<T>' is forbidden. Use 'T[]' instead  @typescript-eslint/array-type

✖ 3 problems (0 errors, 3 warnings)
  0 errors and 3 warnings potentially fixable with the `--fix` option.

```

Exit code: 0. This is not a passing lint result.

Review: git diff --check exited 0. Dash scan of all 11 v2 TypeScript files and package.json passed. No contract, v1, integration, config or other source files were changed.

Correction to the lint note above: the lint command exited 0 with 0 errors and 3 existing v1 warnings, so lint passed with warnings. The CLI added a lint script and an untracked .expo directory; both generated changes were removed immediately. The retained package change is only test:agent:v2. No v1 warnings were edited.

## Stage 03: v2 demo and README

Added the v2 demo, npm script and README section. No testnet calls, credential reads, deployments, installs or account creation were performed. Sandbox checks the wasm file before starting. Existing Stage 01 and 02 sources were not changed.

Initial TypeScript check found helper signature mismatches; these were fixed. Final checks below use npm offline mode to prevent package downloads.

### `npx tsx scripts/demo-v2.ts --network sandbox`

```text
Oralys v2 keyword requests on sandbox. SAMPLE DATA only.
NEAR is Oralys's home chain. Tracks: Agent Economy, Open Innovation and Privacy.
ENOENT: no such file or directory, open '/Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/contract-v2/target/near/oralys_signal_market_v2.wasm'
```
Exit: 1

### `npx tsc --noEmit`

```text
(no output)
```
Exit: 0

### `npx expo lint`

```text

ESLint has been configured 🎉


/Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/agent/src/env.ts
  17:13  warning  Array type using 'Array<T>' is forbidden. Use 'T[]' instead  @typescript-eslint/array-type

/Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/agent/src/near.ts
  13:11  warning  Array type using 'Array<T>' is forbidden. Use 'T[]' instead  @typescript-eslint/array-type

/Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/scripts/demo-v2.ts
  26:21  warning  Array type using 'Array<T>' is forbidden. Use 'T[]' instead  @typescript-eslint/array-type

/Users/agentuser/BeansHQ/oralys-app/_near-s3/oralys-v2/scripts/demo.ts
  21:17  warning  Array type using 'Array<T>' is forbidden. Use 'T[]' instead  @typescript-eslint/array-type

✖ 4 problems (0 errors, 4 warnings)
  0 errors and 4 warnings potentially fixable with the `--fix` option.

```
Exit: 0

### `python3 -I _tools/links.py`

```text
scanned AGENTS.md
scanned CLAUDE.md
scanned CONTEXT.md
scanned stages/05_intents_quote/CONTEXT.md
scanned stages/03_settle/CONTEXT.md
scanned stages/01_intake/CONTEXT.md
scanned stages/04_report/CONTEXT.md
scanned stages/02_evaluate/CONTEXT.md
FAIL: 2 of 59 paths do not resolve
  AGENTS.md: .keys/
  stages/03_settle/CONTEXT.md: contract/target/near/oralys_signal_market.wasm
```
Exit: 1

### `cd contract-v2 && cargo test`

```text
/bin/sh: cargo: command not found
```
Exit: 127

### `npm run build:contract:v2`

```text

> oralys-near-signal-market@0.1.0 build:contract:v2
> cd contract-v2 && cargo near build non-reproducible-wasm

sh: cargo: command not found
```
Exit: 127

Sandbox end-to-end behavior remains unverified: no wasm build is available. Rust commands still needed: `cd contract-v2 && cargo test`, `npm run build:contract:v2`, and `cd contract && cargo test`. After the build, run `npm run test:sandbox:v2` and `npx tsx scripts/demo-v2.ts --network sandbox`. Expo lint is a workspace-required check, but this NEAR repo has no local Expo installation.

Correction to the preceding Expo note: `npx expo lint` resolved an available Expo CLI and completed with four warnings, as its exact output above shows. It added a lint script and a temporary `.expo/` directory; both incidental changes were removed. No packages were installed. The links check failed because `.keys/` and the v1 wasm are absent. Those protected paths were left untouched.

### Session-wide dash scan

Command: `grep -rnP "\x{2014}|\x{2013}"` on all 22 changed or new files across Stages 01, 02 and 03.

```text
grep: invalid option -- P
usage: grep [-abcdDEFGHhIiJLlMmnOopqRSsUVvwXxZz] [-A num] [-B num] [-C[num]]
	[-e pattern] [-f file] [--binary-files=value] [--color=when]
	[--context[=num]] [--directories=action] [--label] [--line-buffered]
	[--null] [pattern] [file ...]
```
Exit: 2 (grep returns 1 for no matches).

The required grep command could not run: the macOS grep has no `-P` option (exit 2, not a clean scan). An equivalent Python scan for code points U+2014 and U+2013 across all 22 session-changed files found 0 hits.

### Commit and diff snapshot

Taken after the Stage 03 commit, before amending that commit to append this snapshot. The Stage 03 hash below is the pre-amend hash; the final hash is in the delivered git history.

`git log --oneline v2-keyword..openclaw/session-3`

```text
573f971 session 3 stage 03: v2 demo script and README
70eac5f session 3 stage 02: v2 query, matcher, excerpts and oracle
64b53dd session 3 stage 01: contract-v2 and sandbox tests
```

`git diff --stat v2-keyword..openclaw/session-3`

```text
 README.md                            |  52 ++++-
 agent/src/v2/buyer-v2.ts             |  25 +++
 agent/src/v2/excerpt.test.ts         | 115 ++++++++++
 agent/src/v2/excerpt.ts              |  52 +++++
 agent/src/v2/feed-v2.ts              |  56 +++++
 agent/src/v2/matcher.test.ts         |  38 ++++
 agent/src/v2/matcher.ts              |  22 ++
 agent/src/v2/oracle-v2.test.ts       |  41 ++++
 agent/src/v2/oracle-v2.ts            |  44 ++++
 agent/src/v2/query.test.ts           |  52 +++++
 agent/src/v2/query.ts                |  93 ++++++++
 agent/src/v2/seller-v2.ts            |  21 ++
 contract-v2/Cargo.toml               |  25 +++
 contract-v2/rust-toolchain.toml      |   3 +
 contract-v2/src/lib.rs               | 252 ++++++++++++++++++++++
 contract-v2/src/tests.rs             | 296 +++++++++++++++++++++++++
 demo-output/demo-v2-sandbox-txs.json |   1 +
 demo-output/demo-v2-sandbox.log      |   3 +
 integration-tests/market-v2.test.ts  | 171 +++++++++++++++
 notes/openclaw-session-3.md          | 405 +++++++++++++++++++++++++++++++++++
 package.json                         |   7 +-
 scripts/demo-v2.ts                   | 157 ++++++++++++++
 22 files changed, 1929 insertions(+), 2 deletions(-)
```
