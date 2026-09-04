from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECKER = Path(__file__).with_name("check_public_boundary.py")


class PublicBoundaryTest(unittest.TestCase):
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

    def test_clean_tracked_source_passes(self) -> None:
        temporary, root = self.make_repo()
        with temporary:
            (root / "README.md").write_text("# Synthetic fixture\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("public_boundary_ok", result.stdout)

    def test_unignored_binary_artifacts_fail(self) -> None:
        temporary, root = self.make_repo()
        with temporary:
            names = ("Compiled.class", "classes.dex", "debug.keystore", "package.apk.idsig")
            for name in names:
                (root / name).write_bytes(b"synthetic")

            result = self.run_checker(root)

        self.assertNotEqual(result.returncode, 0)
        for name in names:
            self.assertIn(f"{name}: forbidden unignored generated/binary artifact", result.stdout)

    def test_unignored_generated_directory_fails(self) -> None:
        temporary, root = self.make_repo()
        with temporary:
            generated = root / "example" / "build" / "generated.txt"
            generated.parent.mkdir(parents=True)
            generated.write_text("synthetic\n", encoding="utf-8")

            result = self.run_checker(root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("forbidden unignored generated build state", result.stdout)

    def test_ignored_build_output_passes(self) -> None:
        temporary, root = self.make_repo()
        with temporary:
            (root / ".gitignore").write_text("build/\n", encoding="utf-8")
            generated = root / "build" / "debug.keystore"
            generated.parent.mkdir()
            generated.write_bytes(b"synthetic")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)

            result = self.run_checker(root)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_tracked_generated_file_fails_even_when_ignored_later(self) -> None:
        temporary, root = self.make_repo()
        with temporary:
            generated = root / "build" / "generated.txt"
            generated.parent.mkdir()
            generated.write_text("synthetic\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "--force", "build/generated.txt"], check=True)
            (root / ".gitignore").write_text("build/\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore"], check=True)

            result = self.run_checker(root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("forbidden tracked generated build state", result.stdout)

    def test_git_inventory_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_checker(Path(directory))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("git inventory unavailable", result.stdout)


if __name__ == "__main__":
    unittest.main()
