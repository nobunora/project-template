# Scripts

Put repo-specific automation here.

See `docs/09_scripts.md` for the standard script contract and recommended run order.

## Deterministic Repository Tools

This template includes two Python 3 utilities with no model/API dependency:

```text
repo_query.py  repository file/text/symbol/reference discovery
analyze.py     C/C++ clang-tidy orchestration and normalized findings
```

Environment checks:

```bash
python3 scripts/repo_query.py doctor
python3 scripts/analyze.py doctor
```

Build the Ctags index:

```bash
python3 scripts/repo_query.py index
```

Typical queries:

```bash
python3 scripts/repo_query.py text TargetSymbol
python3 scripts/repo_query.py symbol TargetSymbol
python3 scripts/repo_query.py refs TargetSymbol
```

Typical analysis:

```bash
python3 scripts/analyze.py fast
python3 scripts/analyze.py normal
python3 scripts/analyze.py deep
```

See `docs/17_repo_index_and_query.md` and `docs/18_static_analysis.md` for setup, output contracts, and failure behavior.
