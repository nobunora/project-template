# Repository Index and Query Environment

Use this document when a repository is large enough that repeated source traversal by an AI agent is wasteful, or when semantic symbol/reference lookup should be delegated to the development machine.

The goal is to make repository discovery cheap, deterministic where possible, and concise. The index is an acceleration layer; the source tree remains authoritative.

## Architecture

Prefer a layered index rather than one tool pretending to answer every question.

```text
source tree
   |
   +--> git / rg ------------------------> lexical file and text search
   |
   +--> Universal Ctags -----------------> language-neutral symbol definitions
   |
   +--> compile_commands.json
             |
             +--> clangd background index -> C/C++ symbols, refs, relations
             +--> clang-tidy               -> static analysis (see 18_static_analysis.md)

repo_query = stable CLI facade over the available layers
```

For C/C++, `compile_commands.json` is the key shared artifact. clangd uses it to parse translation units correctly and builds a cached background index. clang-tidy can consume the same compilation database.

## Required Baseline

Install the following on the machine that holds the working tree:

- Git;
- ripgrep (`rg`);
- Python 3 for the wrapper implementation;
- `jq` if shell-side JSON inspection is useful;
- Universal Ctags for language-neutral symbol indexing.

For C/C++ repositories also install:

- a recent LLVM/Clang toolchain;
- `clangd`;
- `clang-tidy` if static analysis will also be enabled.

Package names vary by distribution. On Debian/Ubuntu-family systems a typical starting point is:

```bash
sudo apt update
sudo apt install git ripgrep python3 jq universal-ctags clangd clang-tidy
```

Verify the actual binaries rather than assuming the package install succeeded:

```bash
git --version
rg --version
ctags --version
clangd --version
clang-tidy --version
python3 --version
```

For long-lived environments, pin the LLVM major version used by CI or the project rather than silently changing analyzer/index behavior during an OS upgrade.

## Generated Data Location

Keep project-owned indexes and query output out of normal repository reads.

Recommended project-owned locations:

```text
.cache/repo-index/
artifacts/repo-query/
```

Let clangd own its background-index cache location. clangd normally stores project index shards under `.cache/clangd/index/` next to the discovered `compile_commands.json`; therefore a database in `build/` commonly results in cache data below `build/.cache/clangd/index/`.

Do not commit generated indexes or query artifacts. If the project places `compile_commands.json` in an ignored `build/` directory, leave it there rather than copying it into the repository root unless a tool requires otherwise.

## Step 1 — Establish Fast Lexical Search

Before semantic indexing, make sure the cheapest operations are reliable.

Examples:

```bash
rg --files
rg -n --hidden --glob '!build/**' --glob '!artifacts/**' 'TargetSymbol'
git grep -n 'TargetSymbol'
```

The wrapper SHOULD prefer lexical search for:

- filenames;
- literals;
- configuration keys;
- error messages;
- comments;
- generated-code markers;
- exact symbol-name discovery before a semantic query.

Do not launch an LSP server merely to answer a query that `rg` can answer precisely.

## Step 2 — Build a Language-Neutral Symbol Index

Universal Ctags is the baseline symbol-definition index.

Create the cache directory and generate JSON when the installed ctags build supports JSON output:

```bash
mkdir -p .cache/repo-index
ctags --output-format=json --fields=+nK -R src tests > .cache/repo-index/ctags.json
```

Adapt indexed paths to the repository. Do not index dependencies, build output, generated artifacts, virtual environments, or vendored trees unless they are part of the task.

If JSON output is unavailable, use the normal tags format and make the wrapper report that limitation. Do not silently parse a different format as JSON.

Universal Ctags is useful for definitions across many languages, but it is not sufficient evidence for semantic callers/callees in C/C++. Use the clangd layer for those operations.

## Step 3 — Generate `compile_commands.json` for C/C++

clangd and clang-tidy need the real compilation flags to understand includes, defines, language mode, target flags, and generated headers.

For CMake projects:

```bash
cmake -S . -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
```

Expected result:

```text
build/compile_commands.json
```

clangd normally searches parent directories and common `build/` subdirectories for this file. If the project uses an unusual layout, configure the compilation-database location explicitly instead of copying stale databases between directories.

For non-CMake projects, use the build system's native compilation-database support or a capture tool such as Bear where appropriate. The generated database MUST represent the same compile flags used by the actual build.

Sanity-check the database:

```bash
python3 -c "import json; p='build/compile_commands.json'; d=json.load(open(p)); print(len(d)); print(d[0]['file'] if d else 'EMPTY')"
```

A syntactically valid but stale compilation database is worse than a missing one because it can make semantic results look authoritative while using the wrong build configuration.

## Step 4 — Warm the clangd Background Index

clangd's background index parses translation units from the compilation database and caches index shards on disk. It provides whole-project symbol, reference, and relation data used by semantic language-server operations.

The simplest operational model is:

1. ensure `compile_commands.json` exists;
2. start clangd through an editor, a small LSP client, or the `repo_query` service;
3. allow background indexing to complete;
4. reuse the cache on subsequent starts.

For the normal background-index path, do not invent a separate database format. Let clangd own its index cache.

For very large repositories or a dedicated analysis server, a static index produced by `clangd-indexer` or a remote clangd index server MAY be introduced later. Start with the background index unless measurements show that startup/indexing cost is material.

## Step 5 — Implement the `repo_query` Facade

`repo_query` is a project-defined CLI contract, not an LLVM binary. Its purpose is to hide tool-specific details from Codex or another lead agent.

Recommended commands:

```text
repo_query files <pattern>
repo_query text <pattern>
repo_query symbol <name>
repo_query refs <name-or-location>
repo_query callers <name-or-location>
repo_query callees <name-or-location>
repo_query related <name-or-location>
repo_query tests <name-or-path>
repo_query changed
repo_query doctor
```

Suggested backend routing:

| Command | Preferred backend | Fallback |
| --- | --- | --- |
| `files` | `rg --files` | Git file list |
| `text` | `rg` | `git grep` |
| `symbol` | clangd for supported semantic languages | Ctags |
| `refs` | clangd/LSP semantic references | clearly labeled lexical `rg` |
| `callers` | language-server/AST call hierarchy when supported | none; report unsupported |
| `callees` | language-server/AST call hierarchy when supported | none; report unsupported |
| `related` | clangd relations/type hierarchy where supported | Ctags/lexical hints |
| `tests` | repository-specific test discovery plus `rg` | `rg` |
| `changed` | Git | none |

Never present a lexical text match as a semantic reference without labeling it as lexical.

## Output Contract

Default to concise machine-readable output. JSON is preferred for agent consumption.

Example:

```json
{
  "query": "process_adc",
  "mode": "symbol",
  "backend": "clangd",
  "semantic": true,
  "definitions": [
    {"path": "src/adc.c", "line": 214, "column": 5}
  ],
  "references": [
    {"path": "src/main.c", "line": 393, "column": 9}
  ],
  "truncated": false
}
```

Every result SHOULD identify:

- backend used;
- whether the result is semantic or lexical;
- path and focused location;
- whether output was truncated;
- index freshness when known.

Do not return entire files by default. Return locations and short evidence so the lead agent can open only the relevant ranges.

## Freshness and Invalidations

The query layer SHOULD detect or expose stale state.

Rebuild or refresh when:

- the active branch changes materially;
- build flags or toolchain settings change;
- `compile_commands.json` changes;
- generated headers change;
- large refactors move symbols;
- the index reports paths that no longer exist.

Ctags indexes SHOULD be regenerated explicitly after material source changes. clangd background-index shards are incrementally maintained by clangd, but the wrapper SHOULD still expose a health/freshness check.

## `repo_query doctor`

Provide a cheap diagnostic command before relying on semantic results.

It SHOULD check at least:

```text
[ ] repository root resolved
[ ] rg available
[ ] git available
[ ] ctags available and expected output format supported
[ ] compile_commands.json present when C/C++ semantic queries are enabled
[ ] clangd available
[ ] compilation database parses
[ ] representative source file exists in the compilation database
[ ] index/cache directories writable
[ ] generated/cache paths are ignored by Git
```

The doctor command should fail clearly when semantic queries are requested but only lexical fallback is available.

## Codex Usage Policy

Prefer this order:

1. `repo_query` to locate relevant files/symbols;
2. read focused source ranges;
3. reason from source and specifications;
4. request broader repository traversal only when evidence requires it.

`repo_query` is a discovery accelerator, not an authority. Final correctness claims MUST still be grounded in the current source, tests, specifications, and execution evidence.

## Scaling to a Dedicated Analysis Machine

A machine with many CPU cores, large RAM, fast SSD, and remote access is well suited to hosting the index.

Recommended separation:

```text
Codex / lead agent
       |
       | concise query
       v
repo_query on analysis host
       |
       +-- rg / Git
       +-- Ctags index
       +-- clangd + compile database
       |
       v
small JSON result with source locations
```

Do not copy multi-gigabyte index internals into prompts. Keep the index server-side and return only query results.

## References

- clangd index design: <https://clangd.llvm.org/design/indexing>
- clangd installation and compilation database setup: <https://clangd.llvm.org/installation>
- clangd configuration: <https://clangd.llvm.org/config>
- Universal Ctags documentation: <https://docs.ctags.io/en/latest/man/ctags.1.html>
- See also `18_static_analysis.md` and `19_local_agent_interfaces.md`.
