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
- Do not parallelize checks that fight with the same watcher, browser, or dev server.
- If a test or command cannot run, give the exact reason and the command a human should run.
- Keep generated, cache, build, log, and artifact paths out of normal reads.
