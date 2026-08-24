#!/usr/bin/env python3
"""Deterministic repository discovery CLI.

Backends:
- Git/ripgrep for lexical discovery
- Universal Ctags JSON for symbol definitions
- clangd LSP for semantic references and call hierarchy

The tool never presents lexical matches as semantic results.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Iterable

DEFAULT_INDEX = Path(".cache/repo-index/ctags.json")
DEFAULT_BUILD_DIRS = ("build", "out/build", "cmake-build-debug", "cmake-build-release")


class ToolError(RuntimeError):
    pass


def run(argv: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as exc:
        raise ToolError(f"required executable not found: {argv[0]}") from exc


def repo_root(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    cp = run(["git", "rev-parse", "--show-toplevel"], cwd=start)
    if cp.returncode != 0:
        raise ToolError(cp.stderr.strip() or "not inside a Git repository")
    return Path(cp.stdout.strip()).resolve()


def find_compile_db(root: Path, explicit: str | None = None) -> Path | None:
    if explicit:
        p = (root / explicit).resolve() if not Path(explicit).is_absolute() else Path(explicit)
        if p.is_dir():
            p = p / "compile_commands.json"
        return p if p.is_file() else None
    candidates = [root / "compile_commands.json"]
    candidates.extend(root / d / "compile_commands.json" for d in DEFAULT_BUILD_DIRS)
    for p in candidates:
        if p.is_file():
            return p.resolve()
    for p in root.glob("**/compile_commands.json"):
        if not any(part in {".git", "node_modules", ".venv"} for part in p.parts):
            return p.resolve()
    return None


def rel(root: Path, path: Path | str) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(root).as_posix()
    except Exception:
        return p.as_posix()


def emit(obj: Any, pretty: bool = True) -> None:
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=2 if pretty else None)
    sys.stdout.write("\n")


def list_files(root: Path, pattern: str | None) -> dict[str, Any]:
    cp = run(["rg", "--files"], cwd=root)
    if cp.returncode not in (0, 1):
        raise ToolError(cp.stderr.strip() or "rg --files failed")
    files = [line for line in cp.stdout.splitlines() if line]
    if pattern:
        p = pattern.lower()
        files = [f for f in files if p in f.lower() or fnmatch.fnmatch(f, pattern)]
    return {"mode": "files", "backend": "ripgrep", "semantic": False, "count": len(files), "files": files}


def rg_json(root: Path, pattern: str, globs: list[str] | None = None, max_results: int = 200) -> dict[str, Any]:
    argv = ["rg", "--json", "-n", "--hidden", "--glob", "!.git/**", "--glob", "!build/**",
            "--glob", "!artifacts/**", "--glob", "!.cache/**"]
    for g in globs or []:
        argv += ["--glob", g]
    argv.extend([pattern, "."])
    cp = run(argv, cwd=root)
    if cp.returncode not in (0, 1):
        raise ToolError(cp.stderr.strip() or "ripgrep failed")
    matches: list[dict[str, Any]] = []
    for line in cp.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("type") != "match":
            continue
        data = item["data"]
        path = data["path"].get("text", "")
        if path.startswith("./"):
            path = path[2:]
        submatches = data.get("submatches") or []
        column = int(submatches[0].get("start", 0)) + 1 if submatches else None
        matches.append({
            "path": path,
            "line": data.get("line_number"),
            "column": column,
            "text": (data.get("lines", {}).get("text") or "").rstrip("\r\n"),
        })
        if len(matches) >= max_results:
            break
    return {"mode": "text", "query": pattern, "backend": "ripgrep", "semantic": False,
            "truncated": len(matches) >= max_results, "matches": matches}


def ctags_supports_json(root: Path) -> bool:
    cp = run(["ctags", "--list-features"], cwd=root)
    return cp.returncode == 0 and "json" in cp.stdout.split()


def build_ctags_index(root: Path, index_path: Path, paths: list[str]) -> dict[str, Any]:
    if not ctags_supports_json(root):
        raise ToolError("installed ctags does not advertise JSON output; Universal Ctags with +json is required")
    index_abs = root / index_path
    index_abs.parent.mkdir(parents=True, exist_ok=True)
    scan_paths = [p for p in paths if (root / p).exists()] or ["."]
    argv = ["ctags", "--output-format=json", "--fields=+nK", "--exclude=.git", "--exclude=build",
            "--exclude=artifacts", "--exclude=.cache", "--exclude=node_modules", "--exclude=.venv",
            "-R", *scan_paths]
    cp = run(argv, cwd=root)
    if cp.returncode != 0:
        raise ToolError(cp.stderr.strip() or "ctags indexing failed")
    tmp = index_abs.with_suffix(index_abs.suffix + ".tmp")
    tmp.write_text(cp.stdout, encoding="utf-8")
    tmp.replace(index_abs)
    return {"mode": "index", "backend": "universal-ctags", "semantic": False,
            "index": rel(root, index_abs), "records": sum(1 for line in cp.stdout.splitlines() if line.startswith("{"))}


def load_ctags(root: Path, index_path: Path) -> Iterable[dict[str, Any]]:
    p = root / index_path
    if not p.is_file():
        raise ToolError(f"ctags index not found: {rel(root, p)}; run `python3 scripts/repo_query.py index` first")
    with p.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def symbol_query(root: Path, index_path: Path, name: str, max_results: int = 100) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for item in load_ctags(root, index_path):
        if item.get("_type") not in (None, "tag") or item.get("name") != name:
            continue
        entry = {"name": item.get("name"), "path": item.get("path"), "line": item.get("line"),
                 "kind": item.get("kind"), "scope": item.get("scope"), "language": item.get("language")}
        matches.append({k: v for k, v in entry.items() if v is not None})
        if len(matches) >= max_results:
            break
    return {"mode": "symbol", "query": name, "backend": "universal-ctags", "semantic": False,
            "truncated": len(matches) >= max_results, "definitions": matches}


def changed_files(root: Path) -> dict[str, Any]:
    names: set[str] = set()
    for argv in (["git", "diff", "--name-only"], ["git", "diff", "--cached", "--name-only"],
                 ["git", "ls-files", "--others", "--exclude-standard"]):
        cp = run(argv, cwd=root)
        if cp.returncode == 0:
            names.update(x for x in cp.stdout.splitlines() if x)
    return {"mode": "changed", "backend": "git", "semantic": False, "files": sorted(names)}


def infer_language_id(path: Path) -> str:
    return {".c": "c", ".h": "cpp", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".hh": "cpp",
            ".hpp": "cpp", ".hxx": "cpp", ".m": "objective-c", ".mm": "objective-cpp"}.get(path.suffix.lower(), "cpp")


def uri_from_path(path: Path) -> str:
    return path.resolve().as_uri()


def path_from_uri(uri: str) -> str:
    from urllib.parse import unquote, urlparse
    parsed = urlparse(uri)
    return unquote(parsed.path) if parsed.scheme == "file" else uri


class LspClient:
    def __init__(self, root: Path, compile_db: Path | None, timeout: float = 30.0):
        self.timeout = timeout
        argv = ["clangd", "--background-index"]
        if compile_db:
            argv.append(f"--compile-commands-dir={compile_db.parent}")
        self.proc = subprocess.Popen(argv, cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL)
        assert self.proc.stdin and self.proc.stdout
        self._stdin, self._stdout = self.proc.stdin, self.proc.stdout
        self._responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self._next_id = 1
        threading.Thread(target=self._reader, daemon=True).start()
        init = self.request("initialize", {"processId": os.getpid(), "rootUri": uri_from_path(root),
            "workspaceFolders": [{"uri": uri_from_path(root), "name": root.name}],
            "capabilities": {"textDocument": {"definition": {"linkSupport": True}, "references": {}, "callHierarchy": {}}}})
        if "error" in init:
            raise ToolError(f"clangd initialize failed: {init['error']}")
        self.notify("initialized", {})

    def _send(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self._stdin.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii") + data)
        self._stdin.flush()

    def _reader(self) -> None:
        try:
            while True:
                headers: dict[str, str] = {}
                while True:
                    line = self._stdout.readline()
                    if not line:
                        return
                    if line in (b"\r\n", b"\n"):
                        break
                    text = line.decode("ascii", errors="replace").strip()
                    if ":" in text:
                        k, v = text.split(":", 1)
                        headers[k.lower()] = v.strip()
                length = int(headers.get("content-length", "0"))
                if length <= 0:
                    continue
                body = self._stdout.read(length)
                if not body:
                    return
                try:
                    self._responses.put(json.loads(body.decode("utf-8")))
                except Exception:
                    continue
        finally:
            self._responses.put({"_eof": True})

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            try:
                msg = self._responses.get(timeout=max(0.05, deadline - time.monotonic()))
            except queue.Empty:
                break
            if msg.get("_eof"):
                raise ToolError("clangd terminated before replying")
            if msg.get("id") == request_id:
                return msg
        raise ToolError(f"clangd request timed out: {method}")

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def open_document(self, path: Path) -> None:
        self.notify("textDocument/didOpen", {"textDocument": {"uri": uri_from_path(path),
            "languageId": infer_language_id(path), "version": 1,
            "text": path.read_text(encoding="utf-8", errors="replace")}})

    def close(self) -> None:
        try:
            self.request("shutdown", {})
            self.notify("exit", {})
        except Exception:
            pass
        try:
            self.proc.terminate()
        except Exception:
            pass


def parse_location(value: str) -> tuple[str, int, int] | None:
    m = re.match(r"^(.*?):(\d+)(?::(\d+))?$", value)
    return (m.group(1), int(m.group(2)), int(m.group(3) or 1)) if m else None


def resolve_location(root: Path, index_path: Path, value: str) -> tuple[Path, int, int]:
    parsed = parse_location(value)
    if parsed:
        p, line, col = parsed
        path = (root / p).resolve()
        if not path.is_file():
            raise ToolError(f"source file not found: {p}")
        return path, line, col
    defs = symbol_query(root, index_path, value, max_results=20)["definitions"]
    candidates = [d for d in defs if d.get("line")]
    if not candidates:
        raise ToolError(f"symbol not found with a source line in ctags index: {value}")
    first = candidates[0]
    path, line_no, column = (root / first["path"]).resolve(), int(first["line"]), 1
    try:
        source_line = path.read_text(encoding="utf-8", errors="replace").splitlines()[line_no - 1]
        match = re.search(rf"\b{re.escape(value)}\b", source_line)
        if match:
            column = match.start() + 1
    except Exception:
        pass
    return path, line_no, column


def lsp_pos(path: Path, line1: int, col1: int) -> dict[str, Any]:
    return {"textDocument": {"uri": uri_from_path(path)},
            "position": {"line": max(0, line1 - 1), "character": max(0, col1 - 1)}}


def normalize_lsp_location(root: Path, loc: dict[str, Any]) -> dict[str, Any]:
    if "targetUri" in loc:
        uri = loc["targetUri"]
        rng = loc.get("targetSelectionRange") or loc.get("targetRange") or {}
    else:
        uri, rng = loc.get("uri", ""), loc.get("range") or {}
    start = rng.get("start") or {}
    return {"path": rel(root, Path(path_from_uri(uri))), "line": int(start.get("line", 0)) + 1,
            "column": int(start.get("character", 0)) + 1}


def semantic_query(root: Path, compile_db: Path, index_path: Path, mode: str, target: str) -> dict[str, Any]:
    path, line, col = resolve_location(root, index_path, target)
    client = LspClient(root, compile_db)
    try:
        client.open_document(path)
        params = lsp_pos(path, line, col)
        if mode == "refs":
            resp = client.request("textDocument/references", {**params, "context": {"includeDeclaration": True}})
            if "error" in resp:
                raise ToolError(str(resp["error"]))
            return {"mode": mode, "query": target, "backend": "clangd", "semantic": True,
                    "origin": {"path": rel(root, path), "line": line, "column": col},
                    "references": [normalize_lsp_location(root, x) for x in (resp.get("result") or [])]}
        prep = client.request("textDocument/prepareCallHierarchy", params)
        if "error" in prep:
            raise ToolError(str(prep["error"]))
        items = prep.get("result") or []
        if not items:
            return {"mode": mode, "query": target, "backend": "clangd", "semantic": True,
                    "origin": {"path": rel(root, path), "line": line, "column": col}, mode: []}
        method = "callHierarchy/incomingCalls" if mode == "callers" else "callHierarchy/outgoingCalls"
        resp = client.request(method, {"item": items[0]})
        if "error" in resp:
            raise ToolError(f"clangd does not support requested call hierarchy operation: {resp['error']}")
        out = []
        for call in resp.get("result") or []:
            node = call.get("from") if mode == "callers" else call.get("to")
            if not node:
                continue
            start = (node.get("selectionRange") or node.get("range") or {}).get("start") or {}
            out.append({"name": node.get("name"), "detail": node.get("detail"),
                        "path": rel(root, Path(path_from_uri(node.get("uri", "")))),
                        "line": int(start.get("line", 0)) + 1, "column": int(start.get("character", 0)) + 1})
        return {"mode": mode, "query": target, "backend": "clangd", "semantic": True,
                "origin": {"path": rel(root, path), "line": line, "column": col}, mode: out}
    finally:
        client.close()


def tests_query(root: Path, pattern: str, max_results: int) -> dict[str, Any]:
    result = rg_json(root, pattern, globs=["tests/**", "test/**", "**/*test*", "**/*spec*"], max_results=max_results)
    result["mode"] = "tests"
    return result


def doctor(root: Path, compile_db_arg: str | None, index_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: str = "", required: bool = True) -> None:
        checks.append({"name": name, "ok": ok, "required": required, "detail": detail})
    add("git", shutil.which("git") is not None, shutil.which("git") or "")
    add("ripgrep", shutil.which("rg") is not None, shutil.which("rg") or "")
    ctags = shutil.which("ctags")
    add("ctags", ctags is not None, ctags or "")
    add("ctags_json", bool(ctags and ctags_supports_json(root)), "Universal Ctags +json required")
    clangd = shutil.which("clangd")
    add("clangd", clangd is not None, clangd or "", required=False)
    db = find_compile_db(root, compile_db_arg)
    db_ok, detail = False, "not found"
    if db:
        try:
            data = json.loads(db.read_text(encoding="utf-8"))
            db_ok = isinstance(data, list) and bool(data)
            detail = f"{rel(root, db)} ({len(data) if isinstance(data, list) else 0} entries)"
        except Exception as exc:
            detail = f"{rel(root, db)}: {exc}"
    add("compile_commands", db_ok, detail, required=False)
    add("ctags_index", (root / index_path).is_file(), rel(root, root / index_path), required=False)
    try:
        (root / index_path).parent.mkdir(parents=True, exist_ok=True)
        writable = os.access((root / index_path).parent, os.W_OK)
    except Exception:
        writable = False
    add("index_directory_writable", writable, rel(root, (root / index_path).parent))
    failed = [c for c in checks if c["required"] and not c["ok"]]
    return {"mode": "doctor", "status": "ok" if not failed else "error", "repository": str(root),
            "checks": checks, "semantic_cpp_available": bool(clangd and db_ok)}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Deterministic repository index/query facade")
    p.add_argument("--compile-db", help="compile_commands.json path or containing directory")
    p.add_argument("--index", default=str(DEFAULT_INDEX), help="ctags JSON index path")
    p.add_argument("--compact", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)
    sp = sub.add_parser("index"); sp.add_argument("paths", nargs="*", default=["src", "include", "tests"])
    sp = sub.add_parser("files"); sp.add_argument("pattern", nargs="?")
    sp = sub.add_parser("text"); sp.add_argument("pattern"); sp.add_argument("--max-results", type=int, default=200)
    sp = sub.add_parser("symbol"); sp.add_argument("name"); sp.add_argument("--max-results", type=int, default=100)
    for name in ("refs", "callers", "callees"):
        sp = sub.add_parser(name); sp.add_argument("target", help="symbol name or path:line[:column]")
    sp = sub.add_parser("tests"); sp.add_argument("pattern"); sp.add_argument("--max-results", type=int, default=200)
    sub.add_parser("changed"); sub.add_parser("doctor")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root, index_path, cmd = repo_root(), Path(args.index), args.command
        if cmd == "index": result = build_ctags_index(root, index_path, args.paths)
        elif cmd == "files": result = list_files(root, args.pattern)
        elif cmd == "text": result = rg_json(root, args.pattern, max_results=args.max_results)
        elif cmd == "symbol": result = symbol_query(root, index_path, args.name, args.max_results)
        elif cmd in ("refs", "callers", "callees"):
            db = find_compile_db(root, args.compile_db)
            if not shutil.which("clangd"): raise ToolError("clangd not found; semantic query unavailable")
            if not db: raise ToolError("compile_commands.json not found; semantic C/C++ query unavailable")
            result = semantic_query(root, db, index_path, cmd, args.target)
        elif cmd == "tests": result = tests_query(root, args.pattern, args.max_results)
        elif cmd == "changed": result = changed_files(root)
        elif cmd == "doctor": result = doctor(root, args.compile_db, index_path)
        else: raise ToolError(f"unknown command: {cmd}")
        emit(result, pretty=not args.compact)
        return 2 if cmd == "doctor" and result.get("status") != "ok" else 0
    except ToolError as exc:
        emit({"status": "error", "error": str(exc)}, pretty=not getattr(args, "compact", False))
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
