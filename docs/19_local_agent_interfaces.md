# Local Agent Interfaces

Use this document to distinguish the local analysis infrastructure from the stable commands exposed to Codex or another lead agent.

The important separation is:

```text
infrastructure != command facade != AI role/orchestration
```

`Repo index/query` and `Static analysis` are environment capabilities. `repo_query`, `analyze`, `local_ai`, and `blind_review` are interfaces/workflows that consume those capabilities.

## Layer Model

```text
Layer 4: orchestration / independent judgment
    blind_review
        |
        | may call
        v
Layer 3: optional probabilistic preprocessing
    local_ai
        |
        | may consume large outputs from lower layers
        v
Layer 2: stable agent-facing deterministic facades
    repo_query             analyze
        |                    |
        v                    v
Layer 1: local infrastructure
    repo index/query       static-analysis environment
    - rg / Git             - compiler diagnostics
    - Ctags                - clang-tidy / analyzer
    - clangd               - lint/type tools
    - compile DB           - compile DB
        \____________________/
                 |
          shared source/build truth
```

The layers may run on the same workstation or on a dedicated analysis host.

## `repo_query`

### What it is

A stable CLI/API facade for repository discovery.

### What it uses

- Git and ripgrep for cheap lexical discovery;
- Universal Ctags for broad symbol definitions;
- clangd or another language server/AST service for semantic symbol/reference relationships;
- repository-specific test/config discovery where configured.

### What it should answer

```text
Where is X defined?
Where is X referenced?
Which files mention this configuration key?
Which callers/callees are known semantically?
Which tests are related to this component?
What changed in this working tree/branch?
```

### What it should not do

- decide whether code is correct;
- classify a design as safe;
- replace source inspection;
- silently convert lexical matches into semantic relationships.

See `17_repo_index_and_query.md`.

## `analyze`

### What it is

A stable CLI/API facade for deterministic lint, type, and static-analysis checks.

### What it uses

- compiler diagnostics;
- clang-tidy/Clang Static Analyzer for C/C++ where configured;
- repository-specific lint/type/static tools;
- Git diff information for fast/changed scoping;
- the same compilation database used by semantic C/C++ indexing.

### What it should answer

```text
Did deterministic checks find a defect or policy violation?
Did this patch introduce new findings?
Which analyzer/check produced the evidence?
Can the normal/deep static-analysis gate pass?
```

### What it should not do

- claim that no bug exists because analyzers pass;
- automatically rewrite all findings;
- suppress raw evidence because an AI disagrees with it.

See `18_static_analysis.md`.

## `local_ai`

### What it is

An optional local-LLM helper for high-volume, low-authority tasks.

It is not the repository index and it is not the static analyzer.

Typical inputs:

- large test logs;
- large analyzer result sets;
- repetitive search results;
- build logs;
- a large diff requiring coarse triage.

Typical outputs:

- clustering;
- deduplication suggestions;
- concise summaries;
- ranking;
- extraction into a fixed JSON schema;
- candidate areas for a stronger reviewer to inspect.

### Authority rule

`local_ai` is probabilistic preprocessing. It MUST NOT silently delete, rewrite, or downgrade deterministic evidence from `analyze` or source facts from `repo_query`.

Preferred pattern:

```text
analyze -> 800 findings/raw lines
        -> local_ai groups them into 12 clusters
        -> lead agent reads original evidence for material clusters
```

Not:

```text
analyze -> local_ai says "probably false positives" -> discard findings
```

A GPU such as an RTX-class card can host this service, but GPU availability is not required by the interface contract.

## `blind_review`

### What it is

An orchestration entry point for the independent review protocol in `16_blind_review_protocol.md`.

It is not simply another analyzer command.

A `blind_review` implementation may:

1. create a fresh reviewer context;
2. provide authoritative requirements and allowed repository inputs;
3. allow the reviewer to call `repo_query` for neutral repository discovery;
4. provide build/test/static-analysis evidence from `analyze`;
5. optionally use `local_ai` for neutral high-volume preprocessing;
6. require a standalone blind report before primary findings are revealed;
7. reconcile blind and primary findings only after the blind phase is complete.

### Independence rule

`blind_review` MUST preserve the independence constraints in `16_blind_review_protocol.md`.

In particular, do not seed repository queries or local-AI prompts with the primary review's suspected defect during the blind phase.

Good:

```text
repo_query refs TargetState
repo_query callers update_target_state
```

Bad during blind review:

```text
repo_query text "known race caused by update_target_state"
```

The tool interface may be automated, but the review is still a reasoning process with explicit evidence and coverage requirements.

## Shared Compilation Database

For C/C++ the cleanest design is:

```text
                    build/compile_commands.json
                         /                 \
                        /                   \
                       v                     v
          repo index/query layer      static-analysis layer
               clangd                    clang-tidy
                   |                         |
                   v                         v
              repo_query                   analyze
```

Do not produce independent compile flag sets for the two paths. A single authoritative compilation database reduces disagreement between symbol discovery and analyzer behavior.

## Recommended Call Order

For normal implementation work:

```text
1. repo_query doctor
2. repo_query ...        # locate and trace only what is needed
3. inspect focused source
4. implement
5. existing build/test
6. analyze fast or normal
7. inspect/fix deterministic findings
8. blind_review if risk/policy requires it
```

When outputs are too large:

```text
repo_query/analyze/raw logs
          |
          v
       local_ai
          |
          v
concise clusters/summary
          |
          v
lead agent verifies material evidence
```

For high-risk independent review:

```text
requirements + current source/diff
          |
          v
     blind_review
          |
          +--> repo_query (neutral discovery)
          +--> analyze evidence
          +--> local_ai only for neutral compression if needed
          |
          v
standalone blind report
          |
          v
post-blind reconciliation
```

## Interface Dependency Matrix

| Interface | Requires repo index/query | Requires static analysis | May use local LLM | Requires independent AI context |
| --- | --- | --- | --- | --- |
| `repo_query` | Yes | No | No | No |
| `analyze` | No, but may share compile DB | Yes | No | No |
| `local_ai` | No | No | It is the local-LLM layer | No |
| `blind_review` | Recommended | Recommended evidence | Optional | Yes when true blind independence is required |

`repo_query` and `analyze` SHOULD remain useful even when `local_ai` is offline. Deterministic development tooling must not depend on an LLM being available.

## Naming and Implementation Guidance

The four names are recommended stable intent-level interfaces, not mandatory implementation technologies.

They may be implemented as:

```text
scripts/repo_query
scripts/analyze
scripts/local_ai
scripts/blind_review
```

or equivalent package-manager commands, Python entry points, shell wrappers, MCP tools, or remote service calls.

Keep the public intent stable even if the backend changes. For example, replacing Ctags with another symbol index should not force Codex instructions to change from `repo_query symbol X` to a backend-specific command.

## Failure Behavior

Every interface SHOULD make degraded operation explicit.

Examples:

- `repo_query` reports `semantic=false` when falling back to lexical search;
- `analyze` returns an environment-error status if the requested analyzer did not run;
- `local_ai` reports unavailable instead of fabricating a summary;
- `blind_review` reports that independence could not be established instead of calling a same-context self-review blind.

## Core Rule

Use deterministic local tools to reduce search and mechanical analysis. Use AI capacity for interpretation, design judgment, and independent review.

The intended division is:

```text
repo_query  = find and trace
analyze     = detect mechanically
local_ai    = compress and triage
blind_review = independently judge
```

See also `15_model_orchestration.md`, `16_blind_review_protocol.md`, `17_repo_index_and_query.md`, and `18_static_analysis.md`.
