# Project Template

[日本語版 / Japanese](README_JP.md)

A language-neutral project template for building software that remains understandable, changeable, and reviewable as the codebase grows — whether the work is performed by humans, AI coding agents, or Codex-style repository agents.

This repository is more than a directory scaffold. It defines a development discipline for **understanding existing intent before changing code, preserving contracts, making the smallest justified change, expressing meaning through types and names, keeping responsibilities local, verifying behavior with evidence, and recording decisions so that future work does not have to reconstruct them from chat history or guesswork**.

The advanced AI/Codex workflow in this repository is built on top of those ordinary engineering rules. The goal is not to replace software design with agents; it is to make good engineering constraints explicit enough that humans and agents can follow the same rules.

## What This Template Is Trying to Achieve

The template is designed to reduce two related classes of failure.

### Code-quality failures

- changing code before understanding why the current code is shaped the way it is;
- rewriting a wide area when a local change would solve the problem;
- mixing feature work, refactoring, formatting, migration, and cleanup in one diff;
- scattering one business rule across several modules, adapters, or entrypoints;
- hiding domain meaning behind generic names such as `manager`, `helper`, `data`, or `process`;
- passing broad dictionaries, framework objects, rows, or loosely typed values across boundaries instead of explicit semantic models;
- using untyped or `any`-style escapes without a strong reason;
- allowing public APIs, persisted fields, configuration keys, units, nullability, or failure behavior to drift accidentally;
- accumulating boolean flags and implicit state until behavior becomes difficult to reason about;
- creating speculative abstractions for hypothetical future needs;
- swallowing errors, leaving temporary bypasses, or adding dependencies without a clear maintenance justification;
- writing code that works today but makes the next change require a large refactor.

### Human/AI workflow failures

- reading too much of the repository and losing the relevant context;
- guessing requirements, compatibility, security behavior, or external contracts;
- starting implementation before confirming that the specification matches repository reality;
- treating passing tests as proof that the implementation matches the requirement;
- letting the implementing agent validate only its own assumptions;
- spending expensive model capacity on search and repetitive analysis that deterministic tools can perform;
- leaving requirements, evidence, decisions, and risks only in chat history.

The central rule is:

> **Understand first. Preserve intent and contracts. Make the smallest coherent change. Express meaning explicitly. Verify with evidence.**

## Core Engineering Philosophy

### 1. Understand existing intent before editing

Start from metadata and targeted search. Identify the responsible component, callers, consumers, state, tests, and contracts that materially affect the requested behavior.

Do not assume that unfamiliar structure is accidental. Existing names, ordering, state transitions, compatibility wrappers, persistence formats, or error handling may encode real constraints.

A change should fit the existing design unless the purpose of the task is explicitly to change that design.

**Result:** fewer accidental regressions and less "rewrite because I did not understand it" behavior.

### 2. Prefer the smallest change that solves the real problem

Keep feature work, refactoring, formatting, migration, and unrelated cleanup separate whenever practical.

A good diff should make it easy to answer:

- what changed;
- why it changed;
- what intentionally did not change;
- which behavior or contract is affected;
- how the change was verified.

For refactors, preserve or characterize current behavior first. Move structure without changing behavior, then change behavior separately when possible.

**Result:** smaller review surfaces, safer rollback, clearer causality, and lower regression risk.

### 3. Design so future changes stay local

The architecture guidance aims to reduce the need for broad future refactoring. It does **not** claim that refactoring will never be necessary. Instead, it tries to make the expected change location predictable.

The key rule is **one meaning, one owner**. A business rule, state transition, fallback order, calculation, validation policy, or presentation meaning should have one authoritative implementation.

Components should have:

- one narrow reason to change;
- explicit ownership and non-ownership;
- deliberate dependency direction;
- small boundary contracts;
- clear state ownership;
- explicit failure behavior.

Adapters translate external details; they should not become second owners of domain policy. Entrypoints coordinate work; they should not become alternate policy implementations. Compatibility layers should delegate to the current owner rather than preserve duplicate logic indefinitely.

**Result:** new requirements usually change one obvious place instead of forcing a repository-wide redesign.

### 4. Make types and contracts carry meaning

Boundaries should communicate semantics, not merely transport data.

Where the language allows it, prefer explicit typed models over broad dictionaries, database rows, framework request objects, or generic payloads passed deep into the system. Important contracts should make clear:

- semantic input and output types;
- units and time basis;
- nullability and missing-data behavior;
- validation ownership;
- error categories;
- retryability and idempotency;
- ordering requirements;
- compatibility and version expectations.

Avoid untyped/`any` escapes unless there is a strong reason. Public APIs, persistent fields, environment keys, protocol fields, and integration names are contracts and should not be renamed merely for style.

This is the sense in which the template favors "fixed" or stable types: **the shape and meaning of data should be explicit and intentional rather than drifting implicitly between components**.

**Result:** fewer invalid states, less ambiguity at module boundaries, better tooling, and easier human/agent reasoning.

### 5. Write code whose intent is visible to humans

Names should expose domain meaning, purpose, state, or units. Prefer specific nouns and explicit verbs that match the vocabulary already used by the project.

Avoid generic names when they conceal responsibility, including `data`, `result`, `item`, `value`, `manager`, `service`, `helper`, `util`, `process`, `execute`, `handle`, and similar catch-all terms.

Comments should explain **why**, constraints, invariants, hardware/protocol quirks, or non-obvious tradeoffs — not narrate obvious mechanics. If a block of code requires a long explanation just to say what it does, improve the boundary, name, or function first.

**Result:** maintainers can infer where a future change belongs without rereading the entire repository.

### 6. Keep state and failure behavior explicit

Mutable state needs a clear owner. Define who may write it, who may read it, whether concurrent writers exist, how stale state is detected, and how partial updates are prevented.

When many booleans begin to encode mutually dependent modes, prefer a state machine or discriminated union over "flag soup". Preserve explicit ordering when reset, initialization, cleanup, save, preview, progress, or workflow sequencing changes behavior.

Do not hide failures as empty results or zero values unless that fallback is a deliberate domain rule. Do not broadly catch and discard exceptions. Fail fast on malformed or unexpected input before expensive work or side effects.

**Result:** behavior remains reconstructable during debugging, review, and recovery.

### 7. Add abstractions and dependencies only for verified reasons

Add an abstraction when it removes real duplication, clarifies a real boundary, or matches an existing design. Do not create layers merely because they might be useful later.

Add a dependency only when the need, maintenance cost, security implications, license, runtime/bundle impact, and testability are acceptable. Prefer existing project tools or the standard library first.

**Result:** less architectural drift and less maintenance debt created in the name of hypothetical flexibility.

### 8. Treat tests and static checks as evidence, not proof

Tests should cover the relevant normal cases, errors, boundaries, empty/missing input, regression cases, compatibility, external failures, timeouts/retries, and permissions where applicable.

Run the checks closest to the changed code first, then widen the scope according to risk. Do not claim a command ran if it did not. If a check cannot run, record the exact reason and the command that remains to be run.

Green tests do not prove architecture quality or specification compliance. Behavior evidence and architecture evidence are separate concerns.

**Result:** verification is honest, reproducible, and proportionate to the change.

## End-to-End Development Flow

```text
request / idea
    |
    v
understand repository intent and constraints
    |
    v
explicit specification for non-trivial work
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
small, bounded implementation
    |
    v
focused checks -> broader tests/static analysis
    |
    v
self-review + affected-path review
    |
    +---- high-risk work ----> independent blind review
    |
    v
record evidence -> merge / release
```

### Repository reading discipline

Read `AGENTS.md`, then `docs/00_index.md`. Use `git status`, shallow listings, `rg`, symbol search, and focused line ranges before whole-file or repository-wide reads.

The indexes under `docs/core/`, `docs/ops/`, and `docs/dev/` are intentionally designed so that an agent or developer opens only the guidance relevant to the current task.

### Specification before implementation

For non-trivial work, use `docs/specs/SPEC_TEMPLATE.md` to define:

- Goal;
- Scope;
- Non-goals;
- Requirements / Invariants;
- Affected Interfaces / Contracts;
- Acceptance Criteria;
- Validation;
- Risks / Rollback;
- Open Questions.

A specification states what must be true. It must not claim compatibility with the repository until repository review validates that claim.

### Deterministic specification gate

When a specification PR is ready for repository review, it may receive the `codex-ready` label. `.github/workflows/spec-ready-gate.yml` checks that a specification changed and that required contract sections exist. The gate does not invoke a model.

### Read-only repository review before implementation

`.codex/repository-review.md` requires the repository agent to inspect affected source, interfaces, execution paths, tests, configuration, persistence/protocol boundaries, and build paths before changing production code.

The disposition must be:

- `validated`;
- `spec-change-required`;
- `blocked`.

Repository review must not silently rewrite product requirements.

### Bounded implementation after validation

`.codex/implementation.md` requires the implementing agent to confirm repository assumptions, derive the smallest reviewable plan, preserve unrelated behavior and contracts, run focused checks first, broaden verification according to risk, and stop when an unapproved contract change or material specification conflict appears.

## Deterministic Repository Discovery

`scripts/repo_query.py` provides a stable JSON-oriented discovery layer.

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

- Git and ripgrep for inexpensive lexical discovery;
- Universal Ctags for language-neutral definition lookup;
- clangd plus `compile_commands.json` for semantic C/C++ references and call hierarchy.

Lexical and semantic evidence are labeled separately. Failed semantic operations do not silently become lexical guesses. Results return locations and short matching lines rather than whole-file dumps.

**Benefit:** source discovery is cheaper, reproducible, and compact enough to feed into a human or AI review without spending unnecessary context.

## Deterministic Static Analysis

`scripts/analyze.py` is the included C/C++ clang-tidy orchestration layer.

```bash
python3 scripts/analyze.py doctor
python3 scripts/analyze.py fast
python3 scripts/analyze.py normal
python3 scripts/analyze.py deep
python3 scripts/analyze.py file src/example.cpp
```

Profiles separate cost and coverage:

- `fast` — changed C/C++ translation units;
- `normal` — changed translation units, conservatively widening after header changes;
- `deep` — every translation unit in `compile_commands.json`;
- `file` — one explicit translation unit.

Diagnostics are normalized to JSON, raw clang-tidy logs are retained, baselines are explicit, and exit codes distinguish findings from environment/tool failures.

For C/C++, `repo_query.py` and `analyze.py` share the same authoritative `compile_commands.json`. The build flags used for semantic discovery and static analysis therefore come from the same source of truth.

## Multi-Agent and Independent Review

`docs/15_model_orchestration.md` separates roles by responsibility:

- **Architect / Adjudicator** — requirements, architecture, conflicts, final judgment;
- **Lead Repository Agent** — real repository inspection, implementation, verification;
- **Delegated Investigator / Implementer** — bounded search or mechanical/localized work;
- **Blind Reviewer** — independent review without inheriting prior conclusions.

Use strong reasoning where judgment materially affects correctness. Use cheaper/faster agents or deterministic tools for bounded traversal and repetitive checks.

For important work, `docs/16_blind_review_protocol.md` uses the rule **Discover first. Compare later.** A blind reviewer reconstructs required behavior and affected paths independently, then primary and blind findings are reconciled afterward.

**Benefit:** less confirmation bias, fewer correlated model errors, and stronger evidence for high-risk changes.

## Complete `docs/` Document Map

The repository intentionally says not to read all of these for every task. This table is an overview so a developer or agent can choose the right document.

| Document | What it defines | Why it matters |
| --- | --- | --- |
| `docs/00_index.md` | Entry index into core, operations, development, and records guidance | Keeps context small; prevents indiscriminate reading |
| `docs/01_principles.md` | Evidence-first work, minimal change, contract discipline, comment discipline | Establishes the default behavior for every change |
| `docs/02_design_and_boundaries.md` | Responsibility separation, thin entrypoints, dependency direction, abstraction rules | Keeps policy in the correct layer and future changes local |
| `docs/03_naming.md` | Domain-specific naming and stability of public/integration names | Makes intent readable and prevents cosmetic contract breakage |
| `docs/04_testing.md` | What to test, focused-to-broad execution order, fixture and reporting rules | Creates honest, risk-based verification |
| `docs/05_safety_and_pokayoke.md` | Hard-coding, validation, secrets, exception handling, security, dependency policy | Prevents common unsafe shortcuts and hidden failure paths |
| `docs/06_code_review.md` | Pre/post implementation review, behavior impact, independent review, convergence | Makes review cover scope, behavior, architecture, and remaining uncertainty |
| `docs/07_bad_patterns.md` | Duplicate logic, hidden intent, `any`/untyped escapes, superficial fixes, noisy diffs | Provides a compact reject-list for maintainability hazards |
| `docs/08_report_template.md` | Standard change/design/test/risk report | Makes work auditable and handoff-friendly |
| `docs/09_scripts.md` | Stable script intent names and serial verification/release behavior | Gives projects a predictable automation contract |
| `docs/10_development_playbook.md` | Work intake, scope control, refactor/implementation/verification/collaboration flow | Turns the principles into an execution order |
| `docs/11_refactor_and_release.md` | Refactor guardrails, stateful UI behavior, release gates, commit rules | Prevents behavioral drift during structural work and release |
| `docs/12_records_and_milestones.md` | When and how to keep milestone, blocker, refactor, and release records | Preserves concise project history and unresolved state |
| `docs/13_architecture_quality.md` | One meaning/one owner, typed boundary contracts, dependency direction, state ownership, change locality, failure containment, observability, compatibility, architecture tests | Main long-form architecture guide for avoiding distributed ownership and large future refactors |
| `docs/14_skill_creation.md` | Contract, structure, validation, evaluation, and safety for reusable Codex Skills | Keeps reusable automation bounded, testable, and unsurprising |
| `docs/15_codebase_memory_and_quality.md` | CodebaseMemory evidence, shared graph artifacts, and quality-audit triage | Prevents graph signals and tool diagnostics from becoming unverified source changes |
| `docs/15_model_orchestration.md` | Role separation, delegation, context separation, model tiers, convergence and escalation | Uses expensive reasoning only where judgment is needed and reduces correlated mistakes |
| `docs/16_blind_review_protocol.md` | Independent first-principles review, adversarial checks, evidence requirements, reconciliation | Prevents primary-review conclusions from biasing the independent reviewer |
| `docs/17_repo_index_and_query.md` | Git/ripgrep/Ctags/clangd indexing and the `repo_query.py` contract | Provides deterministic, targeted source discovery |
| `docs/18_static_analysis.md` | clang-tidy environment, fast/normal/deep scopes, normalized findings, baselines, exit policies | Provides reproducible C/C++ static-analysis gates |
| `docs/19_chat_github_codex_workflow.md` | Specification -> GitHub -> repository review -> Codex implementation -> verification flow | Separates requirements/adjudication from repository execution and preserves the contract in GitHub |
| `docs/core/index.md` | Index for principles, design/boundaries, and naming | Opens only the core rule needed by the current task |
| `docs/ops/index.md` | Index for testing, safety, review, bad patterns, reports, scripts, blind review, static analysis | Routes operational/quality work without loading unrelated guidance |
| `docs/dev/index.md` | Index for workflow, refactor/release, records, skills, orchestration, indexing, and Chat/GitHub/Codex flow | Routes development-process work to the relevant detailed guide |
| `docs/specs/README.md` | Policy for implementation-independent specifications | Makes specifications the durable requirements contract rather than a claim about repository reality |
| `docs/specs/SPEC_TEMPLATE.md` | Required structure for goal, scope, invariants, interfaces, acceptance, validation, risks, questions | Prevents ambiguous specifications from reaching implementation |
| `docs/implementation/README.md` | Policy for repository-review and implementation execution records | Prevents execution notes from becoming a second, silently divergent requirements source |
| `docs/implementation/TASK_TEMPLATE.md` | Repository evidence, approved implementation scope, verification plan/result, risks | Connects a specific specification revision to actual repository evidence and implementation work |
| `docs/records/README.md` | Short chronological milestone/refactor/release/blocker notes | Keeps useful history visible without turning logs into another specification system |

## Supporting Files Outside `docs/`

| Area | Purpose |
| --- | --- |
| `AGENTS.md` | First-read repository rules: search before reading, evidence before assumptions, small diffs, stable contracts, focused verification |
| `.codex/repository-review.md` | Read-only repository-review contract before implementation |
| `.codex/implementation.md` | Implementation contract after repository validation |
| `.codex/README.md` | Entry point for repository-agent contracts |
| `.github/PULL_REQUEST_TEMPLATE/spec.md` | Specification-oriented PR structure |
| `.github/PULL_REQUEST_TEMPLATE/implementation.md` | Implementation-oriented PR evidence structure |
| `.github/workflows/spec-ready-gate.yml` | Deterministic validation of `codex-ready` specification PRs |
| `scripts/README.md` | Entry point for deterministic repository query and static-analysis utilities |
| `scripts/repo_query.py` | Repository file/text/symbol/reference/call discovery |
| `scripts/analyze.py` | C/C++ clang-tidy orchestration and normalized analysis results |

## Standard Script Contract

Projects based on this template can map their native tooling to stable intents:

| Script | Intent |
| --- | --- |
| `doctor` | Environment sanity check |
| `check` | Quick local verification |
| `typecheck` | Static/type checks |
| `test` | Unit/integration tests |
| `build` | Production build/package |
| `refactor:check` | Serial refactor gate |
| `release:check` | Serial release/preflight gate |

These are stable intent names, not a requirement that every ecosystem use the same implementation.

## Practical Benefits

Used consistently, the template is intended to produce these outcomes:

- **Fewer large refactors:** one-owner rules, narrow responsibilities, explicit boundaries, and predictable change locality reduce structural debt before it spreads.
- **More readable code:** domain-specific names, meaningful types, explicit state, and comments about reasons make intent visible to a future maintainer.
- **Safer type and contract evolution:** semantic types, units, nullability, public names, persistence formats, and external interfaces are treated as deliberate contracts rather than incidental implementation details.
- **Smaller, safer changes:** existing behavior and design intent are inspected first, then the smallest coherent diff is preferred.
- **Lower context and token cost:** targeted search and concise deterministic evidence replace indiscriminate repository reads.
- **Less specification drift:** requirements live in GitHub specifications, and implementation stops on material conflicts instead of silently improvising.
- **More reproducible engineering:** query, static analysis, tests, and gates can be rerun and audited.
- **Better AI cost allocation:** strong reasoning is reserved for architecture and adjudication; repetitive discovery/checking can be offloaded.
- **Higher review quality:** review includes affected execution paths and can add a genuinely independent blind pass for high-risk work.
- **Safer refactors and releases:** behavior is protected before structural changes, and verification widens according to risk.
- **Better handoff and auditability:** specifications, implementation records, commands, results, decisions, and residual risks survive beyond one session or one developer.

## Quick Start

1. Use this repository as the base for a new project.
2. Read `AGENTS.md`.
3. Read `docs/00_index.md`, then only the category/document relevant to the task.
4. Before modifying existing code, identify the current owner, callers/consumers, contracts, tests, state, and failure behavior that materially affect the requested change.
5. Keep the implementation as small and local as the existing design permits.
6. Bind the standard script intents to the project's native toolchain.
7. For deterministic repository discovery, follow `docs/17_repo_index_and_query.md` and run `python3 scripts/repo_query.py doctor`.
8. For C/C++ semantic queries or static analysis, generate an accurate `compile_commands.json` from the real build configuration.
9. For non-trivial changes, create a specification under `docs/specs/` before implementation and use `docs/19_chat_github_codex_workflow.md`.
10. Record exact verification evidence, unresolved questions, human confirmation points, and remaining risks before merge/release.

The source tree and approved specification remain authoritative. Indexes, generated analysis data, execution records, AI summaries, and prior review conclusions are supporting evidence; none should silently replace repository reality or redefine the contract.
