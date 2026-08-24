import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


repo_query = load_module("repo_query_test_target", ROOT / "scripts" / "repo_query.py")
analyze = load_module("analyze_test_target", ROOT / "scripts" / "analyze.py")


class RepoQueryTests(unittest.TestCase):
    def test_parse_location(self):
        self.assertEqual(repo_query.parse_location("src/a.cpp:12:7"), ("src/a.cpp", 12, 7))
        self.assertEqual(repo_query.parse_location("src/a.cpp:12"), ("src/a.cpp", 12, 1))
        self.assertIsNone(repo_query.parse_location("foo"))

    def test_symbol_query_reads_ctags_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / ".cache/repo-index/ctags.json"
            index.parent.mkdir(parents=True)
            index.write_text(
                json.dumps({"_type": "tag", "name": "foo", "path": "src/a.cpp", "line": 3, "kind": "function"}) + "\n",
                encoding="utf-8",
            )
            result = repo_query.symbol_query(root, Path(".cache/repo-index/ctags.json"), "foo")
            self.assertEqual(result["backend"], "universal-ctags")
            self.assertFalse(result["semantic"])
            self.assertEqual(result["definitions"][0]["path"], "src/a.cpp")
            self.assertEqual(result["definitions"][0]["line"], 3)


class AnalyzeTests(unittest.TestCase):
    def test_parse_clang_tidy_diagnostic(self):
        root = Path("/tmp/project")
        text = "/tmp/project/src/a.cpp:10:5: warning: object used after move [bugprone-use-after-move]\n"
        findings = analyze.parse_diagnostics(root, text)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.path, "src/a.cpp")
        self.assertEqual(finding.check, "bugprone-use-after-move")
        self.assertEqual(finding.level, "warning")
        self.assertEqual(finding.severity, "medium")

    def test_normal_profile_expands_on_header_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            a = root / "src/a.cpp"
            b = root / "src/b.cpp"
            a.write_text("", encoding="utf-8")
            b.write_text("", encoding="utf-8")
            db_files = {"src/a.cpp": a, "src/b.cpp": b}

            original = analyze.changed_files
            analyze.changed_files = lambda _root: {"include/api.hpp"}
            try:
                selected, meta = analyze.select_translation_units(root, db_files, "normal", None)
            finally:
                analyze.changed_files = original

            self.assertEqual({p.name for p in selected}, {"a.cpp", "b.cpp"})
            self.assertIn("header changed", meta["reason"])

    def test_fail_policy_uses_only_new_findings(self):
        baseline = {"level": "warning", "severity": "medium", "new_in_analysis": False}
        new = {"level": "warning", "severity": "medium", "new_in_analysis": True}
        self.assertFalse(analyze.should_fail([baseline], "any"))
        self.assertTrue(analyze.should_fail([new], "any"))
        self.assertFalse(analyze.should_fail([new], "error"))


if __name__ == "__main__":
    unittest.main()
