#!/usr/bin/env python3
"""Deterministic static-analysis CLI for C/C++ repositories.

Runs clang-tidy against the authoritative compilation database with changed-file
scoping, parallel execution, normalized findings, raw artifacts, and optional
baselines of known finding IDs.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_BUILD_DIRS = ("build", "out/build", "cmake-build-debug", "cmake-build-release")
CPP_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".m", ".mm"}
HEADER_SUFFIXES = {".h", ".hh", ".hpp", ".hxx"}
DIAGNOSTIC_RE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):(?P<column>\d+): "
    r"(?P<level>warning|error|note): (?P<message>.*?)(?: \[(?P<check>[^\]]+)\])?$"
)


class ToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class Finding:
    tool: str
    check: str
    level: str
    severity: str
    path: str
    line: int
    column: int
    message: str

    @property
    def id(self) -> str:
        material = f"{self.tool}\0{self.check}\0{self.path}\0{self.line}\0{self.column}\0{self.message}"
        digest = hashlib.sha1(material.encode("utf-8")).hexdigest()[:12]
        return f"{self.tool}:{self.check}:{self.path}:{self.line}:{digest}"

    def as_dict(self, *, baseline_ids: set[str]) -> dict[str, Any]:
        return {"id": self.id, "tool": self.tool, "check": self.check, "level": self.level,
                "severity": self.severity, "path": self.path, "line": self.line, "column": self.column,
                "message": self.message, "baseline": self.id in baseline_ids,
                "new_in_analysis": self.id not in baseline_ids}


def run(argv: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as exc:
        raise ToolError(f"required executable not found: {argv[0]}") from exc


def repo_root() -> Path:
    cp = run(["git", "rev-parse", "--show-toplevel"], cwd=Path.cwd())
    if cp.returncode != 0:
        raise ToolError(cp.stderr.strip() or "not inside a Git repository")
    return Path(cp.stdout.strip()).resolve()


def rel(root: Path, value: str | Path) -> str:
    p = Path(value)
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return p.as_posix()


def find_compile_db(root: Path, explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = root / p
        if p.is_dir():
            p = p / "compile_commands.json"
        return p.resolve() if p.is_file() else None
    candidates = [root / "compile_commands.json"] + [root / d / "compile_commands.json" for d in DEFAULT_BUILD_DIRS]
    for p in candidates:
        if p.is_file():
            return p.resolve()
    for p in root.glob("**/compile_commands.json"):
        if not any(part in {".git", "node_modules", ".venv"} for part in p.parts):
            return p.resolve()
    return None


def load_compile_db(db_path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(db_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ToolError(f"cannot parse {db_path}: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise ToolError(f"compilation database is empty or invalid: {db_path}")
    return data


def normalize_db_files(root: Path, db: list[dict[str, Any]]) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for item in db:
        file_value = item.get("file")
        if not file_value:
            continue
        directory = Path(item.get("directory") or root)
        p = Path(file_value)
        if not p.is_absolute():
            p = directory / p
        p = p.resolve()
        if p.suffix.lower() in CPP_SUFFIXES:
            out[rel(root, p)] = p
    return out


def changed_files(root: Path) -> set[str]:
    names: set[str] = set()
    for argv in (["git", "diff", "--name-only"], ["git", "diff", "--cached", "--name-only"],
                 ["git", "ls-files", "--others", "--exclude-standard"]):
        cp = run(argv, cwd=root)
        if cp.returncode == 0:
            names.update(x.replace("\\", "/") for x in cp.stdout.splitlines() if x)
    return names


def select_translation_units(root: Path, db_files: dict[str, Path], profile: str,
                             explicit_file: str | None) -> tuple[list[Path], dict[str, Any]]:
    changed = changed_files(root)
    changed_headers = sorted(f for f in changed if Path(f).suffix.lower() in HEADER_SUFFIXES)
    changed_tus = sorted(f for f in changed if f in db_files)
    if profile == "deep":
        selected, reason = list(db_files.values()), "all translation units"
    elif profile == "file":
        if not explicit_file:
            raise ToolError("file profile requires a path")
        p = Path(explicit_file)
        if not p.is_absolute():
            p = (root / p).resolve()
        key = rel(root, p)
        if key not in db_files:
            if p.suffix.lower() in HEADER_SUFFIXES:
                raise ToolError("header files are not translation units; use `normal` or `deep`")
            raise ToolError(f"file is not present in compile_commands.json: {key}")
        selected, reason = [db_files[key]], f"explicit translation unit: {key}"
    elif profile == "normal":
        if changed_headers:
            selected, reason = list(db_files.values()), "header changed; conservatively analyzing all translation units"
        else:
            selected, reason = [db_files[k] for k in changed_tus], "changed translation units"
    elif profile == "fast":
        selected, reason = [db_files[k] for k in changed_tus], "changed translation units only"
    else:
        raise ToolError(f"unknown profile: {profile}")
    unique = {str(p): p for p in selected}
    selected = [unique[k] for k in sorted(unique)]
    return selected, {"reason": reason, "changed_files": sorted(changed), "changed_headers": changed_headers,
                      "selected_translation_units": [rel(root, p) for p in selected]}


def sanitize_filename(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", path).strip("_") or "root"


def severity_for(level: str, check: str) -> str:
    if level == "error":
        return "high"
    if level == "warning":
        return "high" if check.startswith("clang-analyzer-security") or check.startswith("cert-") else "medium"
    return "low"


def parse_diagnostics(root: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line in text.splitlines():
        match = DIAGNOSTIC_RE.match(line)
        if not match:
            continue
        check, level = match.group("check") or "clang-diagnostic", match.group("level")
        findings.append(Finding("clang-tidy", check, level, severity_for(level, check),
            rel(root, Path(match.group("path"))), int(match.group("line")), int(match.group("column")),
            match.group("message").strip()))
    return findings


def clang_tidy_one(root: Path, db_path: Path, source: Path, checks: str | None, raw_dir: Path) -> dict[str, Any]:
    argv = ["clang-tidy", "-p", str(db_path.parent), str(source)]
    if checks:
        argv += [f"-checks={checks}"]
    cp = run(argv, cwd=root)
    combined = "\n".join(x for x in (cp.stdout, cp.stderr) if x)
    raw_path = raw_dir / f"{sanitize_filename(rel(root, source))}.log"
    raw_path.write_text(combined, encoding="utf-8")
    return {"source": rel(root, source), "returncode": cp.returncode, "raw": rel(root, raw_path),
            "findings": parse_diagnostics(root, combined)}


def load_baseline(root: Path, baseline_path: str | None) -> tuple[set[str], str | None]:
    if not baseline_path:
        return set(), None
    p = Path(baseline_path)
    if not p.is_absolute():
        p = root / p
    if not p.exists():
        return set(), rel(root, p)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ToolError(f"invalid baseline file {rel(root, p)}: {exc}") from exc
    ids = data.get("finding_ids", []) if isinstance(data, dict) else data if isinstance(data, list) else None
    if ids is None:
        raise ToolError("baseline must be a list or an object with finding_ids")
    return {str(x) for x in ids}, rel(root, p)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def should_fail(findings: list[dict[str, Any]], fail_on: str) -> bool:
    new = [f for f in findings if f["new_in_analysis"]]
    if fail_on == "none":
        return False
    if fail_on == "error":
        return any(f["level"] == "error" for f in new)
    if fail_on == "high":
        return any(f["severity"] in {"critical", "high"} for f in new)
    if fail_on == "any":
        return bool(new)
    raise ToolError(f"unknown fail policy: {fail_on}")


def analyze(root: Path, db_path: Path, profile: str, explicit_file: str | None, jobs: int,
            checks: str | None, artifacts_root: Path, baseline_path: str | None,
            fail_on: str) -> tuple[dict[str, Any], int]:
    db_files = normalize_db_files(root, load_compile_db(db_path))
    if not db_files:
        raise ToolError("no C/C++ translation units found in compile_commands.json")
    selected, selection = select_translation_units(root, db_files, profile, explicit_file)
    output_dir, raw_dir = artifacts_root / profile, artifacts_root / profile / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    baseline_ids, baseline_label = load_baseline(root, baseline_path)
    if not selected:
        summary = {"profile": profile, "status": "pass", "message": "no translation units selected",
                   "compile_database": rel(root, db_path), "selection": selection,
                   "counts": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                   "new_findings": 0, "baseline_findings": 0,
                   "results": rel(root, output_dir / "findings.json"), "raw": rel(root, raw_dir)}
        write_json(output_dir / "findings.json", [])
        write_json(output_dir / "summary.json", summary)
        return summary, 0
    results: list[dict[str, Any]] = []
    max_workers = max(1, min(jobs, len(selected)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(clang_tidy_one, root, db_path, source, checks, raw_dir) for source in selected]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    crashed = [r for r in results if r["returncode"] not in (0, 1) and not r["findings"]]
    findings_obj, seen = [], set()
    for result in results:
        for finding in result["findings"]:
            obj = finding.as_dict(baseline_ids=baseline_ids)
            if obj["id"] in seen:
                continue
            seen.add(obj["id"])
            findings_obj.append(obj)
    findings_obj.sort(key=lambda x: (x["path"], x["line"], x["column"], x["check"], x["message"]))
    write_json(output_dir / "findings.json", findings_obj)
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings_obj:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    new_count = sum(1 for f in findings_obj if f["new_in_analysis"])
    if crashed:
        status, exit_code = "error", 3
    elif should_fail(findings_obj, fail_on):
        status, exit_code = "fail", 1
    else:
        status, exit_code = "pass", 0
    summary = {"profile": profile, "status": status, "fail_on": fail_on,
               "compile_database": rel(root, db_path), "jobs": max_workers, "checks_override": checks,
               "baseline": baseline_label, "selection": selection, "counts": counts,
               "new_findings": new_count, "baseline_findings": len(findings_obj) - new_count,
               "analyzer_failures": [{"source": r["source"], "returncode": r["returncode"], "raw": r["raw"]} for r in crashed],
               "results": rel(root, output_dir / "findings.json"), "raw": rel(root, raw_dir)}
    write_json(output_dir / "summary.json", summary)
    return summary, exit_code


def doctor(root: Path, db_arg: str | None) -> tuple[dict[str, Any], int]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = "", required: bool = True) -> None:
        checks.append({"name": name, "ok": ok, "required": required, "detail": detail})

    add("git", shutil.which("git") is not None, shutil.which("git") or "")
    clang_tidy = shutil.which("clang-tidy")
    add("clang-tidy", clang_tidy is not None, clang_tidy or "")
    db_path = find_compile_db(root, db_arg)
    if db_path:
        try:
            cpp_files = normalize_db_files(root, load_compile_db(db_path))
            add("compile_commands", bool(cpp_files), f"{rel(root, db_path)} ({len(cpp_files)} C/C++ TUs)")
        except ToolError as exc:
            add("compile_commands", False, str(exc))
    else:
        add("compile_commands", False, "not found")
    config = root / ".clang-tidy"
    add(".clang-tidy", config.exists(), rel(root, config), required=False)
    if clang_tidy and config.exists():
        cp = run(["clang-tidy", "--verify-config"], cwd=root)
        add("clang-tidy-config-valid", cp.returncode == 0, (cp.stderr or cp.stdout).strip() or "ok", required=False)
    failed = [c for c in checks if c["required"] and not c["ok"]]
    return {"mode": "doctor", "status": "ok" if not failed else "error", "repository": str(root), "checks": checks}, 0 if not failed else 2


def create_baseline(root: Path, source_path: str, output_path: str) -> dict[str, Any]:
    source = Path(source_path)
    if not source.is_absolute():
        source = root / source
    if not source.is_file():
        raise ToolError(f"findings file not found: {rel(root, source)}")
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ToolError(f"cannot parse findings file: {exc}") from exc
    if not isinstance(data, list):
        raise ToolError("findings file must contain a JSON array")
    ids = sorted({str(item["id"]) for item in data if isinstance(item, dict) and item.get("id")})
    output = Path(output_path)
    if not output.is_absolute():
        output = root / output
    write_json(output, {"source": rel(root, source), "finding_ids": ids})
    return {"mode": "baseline", "status": "ok", "source": rel(root, source),
            "output": rel(root, output), "finding_ids": len(ids)}


def build_parser() -> argparse.ArgumentParser:
    default_jobs = max(1, (os.cpu_count() or 2) // 2)
    p = argparse.ArgumentParser(description="Deterministic static-analysis facade")
    p.add_argument("--compile-db", help="compile_commands.json path or containing directory")
    p.add_argument("--jobs", type=int, default=default_jobs, help=f"parallel clang-tidy jobs (default: {default_jobs})")
    p.add_argument("--checks", help="temporary clang-tidy -checks override; normally use .clang-tidy")
    p.add_argument("--artifacts", default="artifacts/analysis", help="analysis artifact root")
    p.add_argument("--baseline", help="optional JSON baseline containing finding_ids")
    p.add_argument("--fail-on", choices=("any", "high", "error", "none"), default="any")
    p.add_argument("--compact", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("fast")
    sub.add_parser("normal")
    sub.add_parser("deep")
    sp = sub.add_parser("file")
    sp.add_argument("path")
    sub.add_parser("doctor")
    sp = sub.add_parser("baseline")
    sp.add_argument("--from-findings", required=True, dest="from_findings")
    sp.add_argument("--output", required=True)
    return p


def emit(obj: Any, compact: bool) -> None:
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=None if compact else 2)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = repo_root()
        if args.command == "doctor":
            result, code = doctor(root, args.compile_db)
            emit(result, args.compact)
            return code
        if args.command == "baseline":
            result = create_baseline(root, args.from_findings, args.output)
            emit(result, args.compact)
            return 0
        db_path = find_compile_db(root, args.compile_db)
        if not db_path:
            raise ToolError("compile_commands.json not found")
        if not shutil.which("clang-tidy"):
            raise ToolError("clang-tidy not found")
        artifacts = Path(args.artifacts)
        if not artifacts.is_absolute():
            artifacts = root / artifacts
        summary, code = analyze(root, db_path, args.command, args.path if args.command == "file" else None,
                                max(1, args.jobs), args.checks, artifacts, args.baseline, args.fail_on)
        emit(summary, args.compact)
        return code
    except ToolError as exc:
        emit({"status": "error", "error": str(exc)}, getattr(args, "compact", False))
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
