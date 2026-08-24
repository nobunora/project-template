# Static Analysis Environment

Use this document when deterministic analyzers should handle mechanically detectable defects before expensive model review.

The goal is not to maximize warning count. The goal is to produce reproducible, scoped evidence that a lead agent can act on without reading raw analyzer output indiscriminately.

## Architecture

```text
source tree
   |
   +--> compile / language configuration
   |        |
   |        +--> compiler warnings
   |        +--> clang-tidy / Clang Static Analyzer (C/C++)
   |        +--> language-specific lint/type tools
   |
   +--> Git diff ---------------------> changed-file / changed-line scope

analyze = stable CLI facade
   |
   +--> fast
   +--> normal
   +--> deep
   |
   v
normalized findings + raw artifacts
```

For C/C++, reuse the same `compile_commands.json` described in `17_repo_index_and_query.md`. Do not maintain separate compile flags for indexing and static analysis.

## Required Baseline

The machine SHOULD have:

- the project's normal compiler/toolchain;
- Git;
- Python 3 or another small wrapper runtime;
- the repository's existing lint/type/static tools;
- for C/C++, `clang-tidy` and a valid compilation database.

On Debian/Ubuntu-family systems, a typical C/C++ starting point is:

```bash
sudo apt update
sudo apt install clang clang-tidy clang-tools python3
```

Package names and LLVM versions vary. Prefer the LLVM major version used by project CI when reproducibility matters.

Verify:

```bash
clang --version
clang-tidy --version
python3 --version
```

## Step 1 — Make the Build Configuration Authoritative

Static analysis must parse the same program that the compiler builds.

For CMake:

```bash
cmake -S . -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
```

Expected:

```text
build/compile_commands.json
```

Validate it before running analysis:

```bash
python3 -c "import json; p='build/compile_commands.json'; d=json.load(open(p)); print(len(d)); print(d[0]['file'] if d else 'EMPTY')"
```

If compile flags, target defines, generated headers, SDK paths, or toolchain files change, regenerate the database before trusting analyzer results.

## Step 2 — Establish Project Policy

Do not begin with every available check enabled. Define a small policy that separates correctness checks from style churn.

For C/C++, a reasonable starting set is project-dependent but commonly prioritizes:

- `clang-analyzer-*`;
- `bugprone-*`;
- selected `performance-*`;
- selected `portability-*`;
- selected `concurrency-*` when concurrency exists;
- project-required CERT or C++ Core Guidelines checks where applicable.

Treat broad `modernize-*` and `readability-*` groups as opt-in unless the repository explicitly wants those diffs. Their warnings may be valid but can overwhelm correctness review.

Store project configuration in `.clang-tidy` when C/C++ analysis is part of normal development.

Example starting shape:

```yaml
Checks: >
  -*,
  clang-analyzer-*,
  bugprone-*,
  performance-*,
  portability-*
WarningsAsErrors: ''
HeaderFilterRegex: '^(src|include|tests)/'
SystemHeaders: false
```

Tune this for the repository. Do not copy a generic check set into safety-critical or embedded code without reviewing false positives, target assumptions, allocation rules, exceptions, RTTI, concurrency model, and compiler dialect.

Check the configuration itself:

```bash
clang-tidy --verify-config
```

## Step 3 — Define Three Analysis Profiles

### Fast

Run after a local edit or before asking an AI reviewer to inspect the patch.

Target:

- changed source files or translation units;
- compiler diagnostics already produced by the focused build;
- cheap lint/type checks;
- no whole-repository traversal unless the repository is small.

Intent:

```text
seconds to low minutes
```

### Normal

Run before commit/PR handoff for non-trivial changes.

Target:

- affected translation units;
- standard static analyzer policy;
- lint/type checks required by the project;
- focused tests/build checks handled by their existing scripts.

Intent:

```text
broad enough to catch cross-file effects without paying full-release cost
```

### Deep

Run for high-risk changes, release gates, or when a normal pass reveals systemic issues.

Target:

- all translation units;
- deeper analyzer sets approved by the project;
- full type/lint pass;
- repository-specific security or architecture checks;
- sanitizers or dynamic analyzers only if the existing build/test workflow supports them.

Deep analysis is not automatically required for every edit.

## Step 4 — Run clang-tidy in Parallel

clang-tidy consumes a compilation database via `-p <build-path>` and supports project configuration through `.clang-tidy`.

Single translation unit example:

```bash
clang-tidy -p build src/example.cpp
```

For whole-project or regex-scoped operation, use the `run-clang-tidy` helper installed with the LLVM extra tools where available. It is designed to run clang-tidy across the compilation database in parallel.

Typical form:

```bash
run-clang-tidy -p build -j 24
```

Exact helper names differ across distributions, for example `run-clang-tidy`, `run-clang-tidy.py`, or a version-suffixed binary. The environment setup SHOULD resolve the installed path once and have the `analyze` wrapper call that stable resolved command.

Do not enable `--fix`/`-fix` in the default analysis path. Static analysis should report evidence first; the lead agent decides whether and how to change source.

## Step 5 — Add Language-Specific Adapters

`analyze` should be language-neutral even though individual tools are not.

Examples of adapters that MAY be enabled when the repository already uses them:

| Ecosystem | Typical deterministic checks |
| --- | --- |
| C/C++ | compiler warnings, clang-tidy, Clang Static Analyzer, optional cppcheck |
| Python | Ruff, mypy/pyright where configured |
| TypeScript | `tsc --noEmit`, ESLint |
| Rust | `cargo clippy`, compiler warnings |
| Go | `go vet`, configured linters |

Do not add every tool to every project. Prefer existing project tooling and add a dependency only when its signal justifies installation and maintenance cost.

## Step 6 — Implement the `analyze` Facade

`analyze` is a project-defined CLI contract, not one analyzer binary.

Recommended commands:

```text
analyze fast
analyze normal
analyze deep
analyze changed
analyze file <path>
analyze doctor
analyze explain <finding-id>
```

Suggested behavior:

```text
analyze fast
  -> determine changed/affected files
  -> run cheap configured analyzers
  -> normalize findings
  -> print concise summary

analyze normal
  -> run normal policy over affected TUs/components
  -> normalize findings
  -> retain raw logs as artifacts

analyze deep
  -> run approved full-repository policy
  -> normalize findings
  -> retain raw logs and timing data
```

## Normalized Finding Contract

Do not make Codex parse multiple megabytes of heterogeneous analyzer logs if a small structured result is sufficient.

Recommended record:

```json
{
  "id": "clang-tidy:src/control.cpp:417:bugprone-use-after-move",
  "tool": "clang-tidy",
  "check": "bugprone-use-after-move",
  "severity": "high",
  "path": "src/control.cpp",
  "line": 417,
  "column": 9,
  "message": "object used after it was moved",
  "new_in_diff": true,
  "autofix_available": false
}
```

The wrapper MAY add project-level severity mapping, but it MUST preserve the original tool/check identity. Do not convert every warning to High merely because the tool emitted it.

Summary output SHOULD be compact:

```json
{
  "profile": "normal",
  "status": "fail",
  "counts": {"critical": 0, "high": 2, "medium": 7, "low": 11},
  "new_findings": 3,
  "baseline_findings": 17,
  "results": "artifacts/analysis/normal/findings.json",
  "raw": "artifacts/analysis/normal/raw/"
}
```

## Baselines and New Findings

For mature repositories with existing warnings, distinguish:

- findings introduced by the current change;
- existing baseline findings;
- findings whose scope cannot be determined.

Do not hide old Critical/High defects merely because they are baseline. Instead, prevent baseline noise from making every unrelated patch impossible to review.

A useful default gate is:

```text
no new Critical/High findings
+ no unexplained increase in lower-severity findings
+ existing project-required static-analysis gate still passes
```

Repositories with stricter requirements MAY require zero findings.

## Changed-Line Filtering

Changed-line analysis is useful for fast feedback but is not proof that a patch cannot break unchanged code.

A change can alter:

- callers;
- templates;
- generated instantiations;
- shared state;
- compile-time configuration;
- ownership/lifetime assumptions;
- header consumers.

Use changed-line or changed-file scoping as a speed optimization, then expand to affected translation units or full analysis when risk requires it.

## Output and Artifact Policy

Recommended paths:

```text
artifacts/analysis/fast/
artifacts/analysis/normal/
artifacts/analysis/deep/
```

Store:

- normalized `findings.json`;
- concise `summary.json`;
- raw tool output for audit/debugging;
- optional timing/profile output.

Keep artifacts out of normal source scans and out of Git unless the project explicitly snapshots analysis evidence.

## Exit Codes

Define stable exit behavior for automation.

Recommended:

```text
0 = analysis completed and policy passed
1 = analysis completed and policy failed
2 = environment/configuration error
3 = analyzer crashed or produced invalid output
```

Do not return success when the requested analyzer silently failed to start.

## `analyze doctor`

It SHOULD verify at least:

```text
[ ] repository root resolved
[ ] required analyzer binaries available
[ ] versions recorded
[ ] compile_commands.json valid when required
[ ] .clang-tidy parses when present
[ ] representative translation unit can be analyzed
[ ] output/artifact paths writable
[ ] baseline file valid when configured
[ ] generated/artifact/cache paths ignored
```

## Agent Usage Policy

Preferred flow:

```text
implement patch
   |
   v
focused build/test
   |
   v
analyze fast/normal
   |
   +--> deterministic findings -> fix or adjudicate
   |
   +--> large raw output -> local_ai may summarize/classify
   |
   v
independent review / blind_review when required
```

Static analysis is evidence, not proof. Passing analyzers do not replace tests, source review, specification checks, or blind review for high-risk changes.

Do not let `local_ai` suppress deterministic findings. If AI-based triage labels a finding as likely false positive, retain the original finding and evidence until the lead reviewer adjudicates it.

## References

- clang-tidy documentation: <https://clang.llvm.org/extra/clang-tidy/>
- clangd/compile database setup: <https://clangd.llvm.org/installation>
- See also `17_repo_index_and_query.md`, `15_model_orchestration.md`, `16_blind_review_protocol.md`, and `19_local_agent_interfaces.md`.
