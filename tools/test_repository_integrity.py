from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECKER = Path(__file__).with_name("check_repository_integrity.py")


class RepositoryIntegrityTest(unittest.TestCase):
    def make_repo(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        subprocess.run(
            ["git", "init", "--quiet", str(root)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return temporary, root

    def run_checker(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECKER), "--repo-root", str(root)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def add_all(self, root: Path) -> None:
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)

    def test_valid_json_jsonl_and_relative_link_pass(self) -> None:
        temporary, root = self.make_repo()
        with temporary:
            (root / "data.json").write_text('{"synthetic": true}\n', encoding="utf-8")
            (root / "events.jsonl").write_text('{"event": 1}\n\n{"event": 2}\n', encoding="utf-8")
            (root / "target.md").write_text("# Target\n", encoding="utf-8")
            (root / "README.md").write_text(
                "[local](target.md#target) [external](https://example.invalid) [anchor](#section)\n",
                encoding="utf-8",
            )
            self.add_all(root)

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("repository_integrity_ok", result.stdout)

    def test_invalid_json_fails(self) -> None:
        temporary, root = self.make_repo()
        with temporary:
            (root / "broken.json").write_text("{\n", encoding="utf-8")
            self.add_all(root)

            result = self.run_checker(root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("broken.json:", result.stdout)
        self.assertIn("invalid JSON", result.stdout)

    def test_invalid_jsonl_reports_line(self) -> None:
        temporary, root = self.make_repo()
        with temporary:
            (root / "broken.jsonl").write_text('{"ok": true}\nnot-json\n', encoding="utf-8")
            self.add_all(root)

            result = self.run_checker(root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("broken.jsonl:2: invalid JSONL", result.stdout)

    def test_missing_relative_markdown_link_fails(self) -> None:
        temporary, root = self.make_repo()
        with temporary:
            (root / "README.md").write_text("[missing](docs/missing.md)\n", encoding="utf-8")
            self.add_all(root)

            result = self.run_checker(root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("README.md:1: missing relative link target: docs/missing.md", result.stdout)

    def test_relative_markdown_link_cannot_escape_repository(self) -> None:
        temporary, root = self.make_repo()
        with temporary:
            (root / "README.md").write_text("[outside](../)\n", encoding="utf-8")
            self.add_all(root)

            result = self.run_checker(root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("README.md:1: relative link escapes repository root: ../", result.stdout)


if __name__ == "__main__":
    unittest.main()
