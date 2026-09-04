# AGENTS.md

Keep context small and act from evidence.

## Core Rules

- Read this file first.
- Do not scan all docs or all source files.
- Start with metadata: `git status --short`, shallow directory listings, and `rg --files`.
- Use `rg` to find the target before opening files.
- Open only the relevant index, file, and line range.
- Full-file reads are allowed only for short files or when structure is required.
- If broader reading is needed, state why before doing it.
- Follow existing design, names, boundaries, and error handling.
- Do not guess specs, compatibility, security, or external contracts. Verify or ask.
- Do not rename public APIs, DB fields, env keys, or integration fields unless required.
- Keep one main responsibility per file or function.
- Keep diffs small and focused. Do not mix feature work, refactoring, and formatting in one change.
- Do not leave debug code, commented-out code, or temporary bypasses behind.
- Do not add new dependencies unless the need, maintenance cost, and risk are clear.
- Report briefly: changed files, reason, checks run, risks, and open questions.

## Bounded Verification Mode

Use this mode when the task says the design or implementation is already decided or applied and Codex is being used primarily to execute, test, verify, reproduce, measure, or report.

- Treat the supplied implementation and acceptance criteria as the working contract. Do not independently redesign the feature unless verification proves that the contract cannot be satisfied.
- Start from `git status --short`, `git diff --name-only`, and the relevant `git diff`. Do not begin by rediscovering the repository architecture.
- Read the task packet, changed files, directly relevant tests, and only the smallest source ranges needed to understand a failure.
- Default read budget: the task instructions, `AGENTS.md`, changed files, directly relevant tests, plus at most 3 additional source/config files.
- Do not silently exceed the read budget. If more than 3 additional files appear necessary, stop the investigation, report why broader context is required, list the specific files or symbols needed next, and wait for a narrower follow-up task unless the task explicitly authorizes broader investigation.
- Prefer `rg`, symbol search, imports, compiler diagnostics, stack traces, and targeted line ranges. Do not open whole directories, unrelated documentation, history, generated files, caches, build outputs, or large logs merely to gain context.
- Follow evidence outward one hop at a time. A failing test, compiler error, stack trace, direct import, or direct call edge may justify the next read; curiosity alone does not.
- Run the exact requested commands first. Then run the narrowest relevant tests before broader suites unless the acceptance criteria explicitly require a full suite.
- For runtime or hardware verification, prioritize execution evidence: exit status, observed behavior, measurements, concise logs, screenshots/artifacts when requested, and reproducible steps.
- Keep command output small. Quote only diagnostics and log excerpts needed to establish PASS/FAIL or identify the failure.
- Do not perform opportunistic refactoring, cleanup, dependency upgrades, formatting sweeps, or unrelated fixes during verification.
- If a failure has an obvious, local, low-risk fix inside the authorized files, a task may explicitly permit that fix. Otherwise diagnose and report; do not expand into an implementation task on your own.
- After any permitted local fix, rerun the failing check first, then the directly relevant regression checks.
- If the root cause cannot be established within the read budget, report `INCONCLUSIVE` rather than guessing.
- Verification reports should contain: overall result (`PASS`, `FAIL`, or `INCONCLUSIVE`), commands/checks run, relevant environment/version facts, observed versus expected behavior, concise failure evidence, files read beyond the changed set, files modified if any, residual risks, and the smallest recommended next action.

## CodebaseMemory

- Before proposing or implementing a code change, query CodebaseMemory for the target symbol, callers, callees, tests, and dependency boundary. Confirm the index is ready; use targeted source reads and `rg` to verify its findings.
- Treat `in_degree = 0`, low-confidence `CALLS`, similarity, and semantic relations as investigation leads, never as sufficient evidence for deletion, refactoring, or consolidation.
- Before deleting a private helper or compatibility wrapper, check direct and dynamic references, imports, monkeypatches, current contracts, tests, and relevant history.
- Keep source readable: do not rename, wrap, or restructure production code solely to improve graph confidence. Classify resolver mistakes, SDK calls, builtins, test fakes, and intentional dynamic dispatch as graph evidence rather than source defects.
- When a shared `.codebase-memory/graph.db.zst` artifact is tracked, use it as the initial map. Refresh it once after a source-bearing change; commit the generated artifact last, and never refresh again merely because the artifact commit advanced `HEAD`.

## Quality Audit

- Before tests, run applicable independent checks for lint, architecture/import boundaries, types, dependency use, and JavaScript/TypeScript. Record tool versions, commands, exit status, and diagnostics.
- Triage every diagnostic against source and tests before editing. Preserve deliberate re-exports, compatibility seams, dynamic imports, SDK boundaries, and test fakes.
- Run type checkers with the project interpreter. For dependency checks, map distribution names to import names before treating a finding as real (for example `beautifulsoup4`/`bs4` and `scikit-learn`/`sklearn`).
- Keep confirmed project defects separate from missing-tool/configuration gaps and pre-existing advisory diagnostics. Do not add dependencies, suppress rules, or bulk auto-fix merely to make a tool clean.

## Read Next

- `docs/00_index.md`
- Then choose one category index only when needed.

## Working Rules

- Prefer focused tests near the changed code first.
- Prefer `rg`, symbol search, and targeted ranges over full-file reads.
- If behavior might change, say so explicitly.
- If a change touches UI state, save flow, workflow orchestration, preview, progress, or entrypoint wiring, read the refactor and release rules before editing.
- Before creating or modifying a reusable Codex Skill, read `docs/14_skill_creation.md`.
- For multi-model, delegated-agent, iterative review, or blind-review work, read `docs/15_model_orchestration.md`; if blind independence is required, also read `docs/16_blind_review_protocol.md`.
- For local repository indexing/query or deterministic static analysis, read `docs/17_repo_index_and_query.md` and `docs/18_static_analysis.md`.
- For Chat/GitHub specification handoff, repository validation, or specification-to-Codex implementation flow, read `docs/19_chat_github_codex_workflow.md`.
- Do not parallelize checks that fight with the same watcher, browser, or dev server.
- If a test or command cannot run, give the exact reason and the command a human should run.
- Keep generated, cache, build, log, and artifact paths out of normal reads.
