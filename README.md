# Project Template

[日本語版 / Japanese](README_JP.md)

A language-neutral, evidence-driven starter for disciplined software development with humans, AI coding agents, and Codex-style repository agents.

This repository is not only a folder layout. It defines a development control system: requirements are written as explicit contracts, repository reality is checked before implementation, deterministic tools are used for discovery and static analysis, changes are kept bounded, and important work can be reviewed independently before merge.

## Purpose

The template is designed to reduce common failure modes in both human and AI-assisted development:

- reading too much of a repository and losing the relevant context;
- guessing requirements, compatibility, security behavior, or external contracts;
- starting implementation before checking whether the specification matches the real repository;
- silently expanding scope or mixing features, refactors, formatting, and cleanup;
- treating passing tests as proof that the implementation matches the requirement;
- letting an implementing agent review only its own assumptions;
- spending expensive model capacity on repository traversal that deterministic tools can perform more cheaply;
- losing requirements and decisions inside chat history instead of preserving them in GitHub.

The central rule is **evidence first, smallest necessary context, explicit contracts, bounded changes, and verifiable results**.

## End-to-End Workflow

```text
request / idea
    |
    v
explicit specification
    |
    v
specification contract gate
    |
    v
repository review (read-only)
    |
    +---- conflict / missing evidence ----> specification revision
    |
    v
validated implementation contract
    |
    v
bounded implementation
    |
    v
deterministic checks + tests + static analysis
    |
    v
implementation review
    |
    +---- high-risk work ----> independent blind review
    |
    v
record evidence -> merge / release
```

### 1. Start with small, targeted context

Read `AGENTS.md`, then `docs/00_index.md`. Use metadata, `rg`, symbol search, and focused line ranges before opening whole files.

This keeps repository context small and reduces both human search cost and LLM/Codex token consumption.

### 2. Turn requirements into a specification contract

For non-trivial work, put the implementation-independent requirement under `docs/specs/` and define at least:

- Goal;
- Scope;
- Non-goals;
- Requirements / Invariants;
- affected interfaces or contracts;
- Acceptance Criteria;
- Validation;
- risks and rollback considerations when relevant.

GitHub becomes the durable contract layer instead of chat history.

### 3. Gate specifications before repository execution

When a specification PR is ready for repository validation, apply the `codex-ready` label.

`.github/workflows/spec-ready-gate.yml` deterministically checks that the PR changes a specification and contains the required contract sections. The gate intentionally does not invoke a model.

### 4. Review the real repository before implementation

Use `.codex/repository-review.md` for the first repository-agent pass.

The agent inspects actual source, interfaces, execution paths, tests, configuration, persistence/protocol boundaries, and build paths, but **does not modify production code**. The result must be one of:

- `validated`;
- `spec-change-required`;
- `blocked`.

A specification conflict is returned for adjudication instead of being silently reinterpreted by the implementation agent.

### 5. Implement only the validated contract

Use `.codex/implementation.md` after repository review is `validated`.

Implementation is expected to:

- make the smallest reviewable change;
- preserve unrelated behavior and public contracts;
- run focused checks first;
- run broader checks according to risk;
- stop if repository reality materially contradicts the approved specification;
- record exact evidence and residual risk.

### 6. Use deterministic repository discovery

`scripts/repo_query.py` provides a stable JSON-oriented query facade.

```bash
python3 scripts/repo_query.py doctor
python3 scripts/repo_query.py index
python3 scripts/repo_query.py files adc
python3 scripts/repo_query.py text ADC_TIMEOUT
python3 scripts/repo_query.py symbol process_adc
python3 scripts/repo_query.py refs process_adc
python3 scripts/repo_query.py callers process_adc
python3 scripts/repo_query.py callees control_loop
python3 scripts/repo_query.py tests process_adc
python3 scripts/repo_query.py changed
```

It uses:

- Git and ripgrep for cheap lexical discovery;
- Universal Ctags for language-neutral symbol definitions;
- clangd plus `compile_commands.json` for semantic C/C++ references and call hierarchy.

Lexical and semantic evidence are explicitly distinguished. The tool returns locations and short matching lines rather than dumping whole source files.

**Benefit:** repository traversal becomes cheaper, more reproducible, and easier to feed into AI agents without consuming unnecessary context.

### 7. Run deterministic static analysis

`scripts/analyze.py` is the included C/C++ static-analysis wrapper around clang-tidy.

```bash
python3 scripts/analyze.py doctor
python3 scripts/analyze.py fast
python3 scripts/analyze.py normal
python3 scripts/analyze.py deep
python3 scripts/analyze.py file src/example.cpp
```

Profiles intentionally separate cost and coverage:

- `fast` — changed C/C++ translation units;
- `normal` — changed translation units, conservatively widening after header changes;
- `deep` — every translation unit in `compile_commands.json`;
- `file` — one explicit translation unit.

Findings are normalized to JSON, raw analyzer logs are retained, optional baselines are explicit, and exit codes are suitable for automation.

For C/C++, both `repo_query.py` semantic operations and `analyze.py` share the same authoritative `compile_commands.json`, preventing separate tool configurations from drifting apart.

### 8. Separate implementation from independent judgment

`docs/15_model_orchestration.md` defines roles such as:

- Architect / Adjudicator;
- Lead Repository Agent;
- Delegated Investigator / Implementer;
- Blind Reviewer.

Use stronger reasoning capacity for architecture, conflicts, adjudication, and final judgment. Use cheaper/faster agents or deterministic tools for bounded discovery and repetitive checks.

For high-risk changes, `docs/16_blind_review_protocol.md` requires an independent reviewer to reconstruct behavior from the specification and repository **without seeing the primary review's conclusions first**.

**Benefit:** this reduces correlated mistakes, confirmation bias, and self-review blind spots.

### 9. Preserve evidence

Use `docs/08_report_template.md`, `docs/implementation/`, and `docs/records/` to capture:

- changed files and reasons;
- commands executed;
- results;
- validation gaps;
- human confirmation points;
- remaining risks;
- milestone state and next action.

A command that did not run must never be reported as successful.

## What the Repository Contains

| Area | Purpose | Main benefit |
| --- | --- | --- |
| `AGENTS.md` | First-read rules for evidence-first repository work | Smaller context, fewer unsupported assumptions |
| `docs/01`–`07` | Principles, boundaries, naming, testing, safety, review, bad patterns | Consistent engineering discipline |
| `docs/08`–`12` | Reports, script contracts, development flow, release/refactor rules, records | Reproducible execution and audit trail |
| `docs/13_architecture_quality.md` | Ownership, dependency direction, failure containment, architecture tests | Predictable change locality and maintainability |
| `docs/14_skill_creation.md` | Rules for reusable Codex Skills | Safer, reusable agent automation |
| `docs/15_model_orchestration.md` | Multi-role/model workflow and cost discipline | Better separation of judgment and repetitive work |
| `docs/16_blind_review_protocol.md` | Independent review from first principles | Reduced confirmation bias |
| `docs/17_repo_index_and_query.md` | Local repository index/query environment | Fast targeted source discovery |
| `docs/18_static_analysis.md` | Deterministic clang-tidy environment | Repeatable diagnostics and automation gates |
| `docs/19_chat_github_codex_workflow.md` | Chat -> GitHub -> Codex contract handoff | Durable specs and controlled repository execution |
| `.codex/` | Repository-review and implementation contracts | Prevents implementation from silently changing requirements |
| `.github/` | PR templates and deterministic specification gate | Enforces contract readiness before automation |
| `scripts/` | Deterministic repository query and analysis tools | Offloads search/check work from LLMs |

## Core Engineering Rules

Across the documents, the template consistently enforces these rules:

- one business meaning should have one authoritative owner;
- components should have narrow responsibilities and explicit boundaries;
- dependencies should flow deliberately toward domain policy;
- public APIs, persisted fields, environment keys, and integration fields are contracts;
- unknown behavior must be verified rather than guessed;
- feature work, refactoring, formatting, and migration should not be mixed without reason;
- tests should cover normal, error, boundary, regression, compatibility, and external-failure paths as applicable;
- risky input should be validated before expensive work or side effects;
- broad exception swallowing, hidden bypasses, debug code, and unjustified dependencies are prohibited;
- passing tests are evidence, not proof of specification compliance;
- a review with no findings must still describe what was inspected and what remains unverified.

## Standard Script Contract

Projects based on this template can map their native tooling to these stable intents:

| Script | Intent |
| --- | --- |
| `doctor` | Environment sanity check |
| `check` | Quick local verification |
| `typecheck` | Static/type checks |
| `test` | Unit/integration tests |
| `build` | Production build/package |
| `refactor:check` | Serial refactor gate |
| `release:check` | Serial release/preflight gate |

These are contract names, not a requirement that every language ecosystem use the same implementation.

## Quick Start

1. Copy this repository as the base for a new project.
2. Read `AGENTS.md`.
3. Read `docs/00_index.md` and only the category relevant to the task.
4. Bind the standard script intents to the project's actual toolchain.
5. For repository discovery, install the dependencies described in `docs/17_repo_index_and_query.md` and run:

   ```bash
   python3 scripts/repo_query.py doctor
   ```

6. For C/C++ semantic queries or static analysis, generate an accurate `compile_commands.json` from the real build configuration.
7. For non-trivial changes, create a specification before implementation and use the Chat -> GitHub -> Codex flow in `docs/19_chat_github_codex_workflow.md`.
8. Record commands, evidence, risks, and unresolved questions before merge or release.

## Resulting Benefits

Using the template consistently should provide the following practical benefits:

- **Lower context and token cost:** targeted search and concise JSON evidence replace indiscriminate repository reads.
- **Less specification drift:** requirements live in explicit GitHub contracts and implementation stops on material conflicts.
- **More reproducible engineering:** deterministic query, analysis, tests, and gates produce evidence that can be rerun.
- **Better AI cost allocation:** strong reasoning is reserved for architecture and adjudication while search and repetitive checks are offloaded.
- **Higher review quality:** implementation review, affected-path inspection, and optional blind review reduce self-confirmation.
- **Safer refactors and releases:** behavior is protected first, checks widen according to risk, and release gates remain explicit.
- **Cleaner architecture:** one-owner rules, dependency direction, and explicit state/failure contracts make change impact more predictable.
- **Better handoff and auditability:** specifications, implementation records, commands, results, and remaining risks survive beyond one chat session.

## Recommended Reading Order

1. `AGENTS.md`
2. `docs/00_index.md`
3. the relevant core/ops/dev document only
4. `docs/19_chat_github_codex_workflow.md` for specification-to-implementation work
5. `docs/17_repo_index_and_query.md` and `docs/18_static_analysis.md` when deterministic local analysis is needed
6. `docs/15_model_orchestration.md` and `docs/16_blind_review_protocol.md` for complex or high-risk multi-agent work

The source tree remains authoritative. Indexes, generated analysis data, agent summaries, and prior conclusions are supporting evidence and must not silently replace repository reality or the approved specification.
