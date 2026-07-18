import pathlib
import re
import shutil
import subprocess
import os
import unittest
import xml.etree.ElementTree as ET


ROOT = pathlib.Path(__file__).resolve().parent
HELPER = ROOT / "quest-inkscape-print"
LAUNCHER = ROOT / "quest-inkscape-print.desktop"
INSTALLER = ROOT / "install-quest-inkscape-print.sh"
FIXTURE = ROOT.parent / "fixtures" / "print-smoke.svg"


class QuestInkscapePrintTests(unittest.TestCase):
    def test_shell_scripts_parse(self):
        for script in (HELPER, INSTALLER):
            if os.name == "nt":
                wsl = shutil.which("wsl")
                if wsl is None:
                    self.skipTest("WSL is not available")
                command = [wsl, "bash", "-n"]
                result = subprocess.run(
                    command,
                    input=script.read_bytes(),
                    capture_output=True,
                    check=False,
                )
                stderr = result.stderr.decode("utf-8", errors="replace")
            else:
                bash = shutil.which("bash")
                if bash is None:
                    self.skipTest("bash is not available")
                command = [bash, "-n", str(script)]
                result = subprocess.run(
                    command, capture_output=True, text=True, check=False
                )
                stderr = result.stderr
            self.assertEqual(result.returncode, 0, stderr)

    def test_helper_is_bounded_and_loopback_only(self):
        source = HELPER.read_text(encoding="utf-8")
        self.assertIn('DEFAULT_CUPS_SERVER="127.0.0.1:8631"', source)
        self.assertIn('work_dir=$(mktemp -d', source)
        self.assertIn("--file-selection", source)
        self.assertIn("--export-width=1240", source)
        self.assertIn('print-color-mode="$color_mode"', source)
        self.assertIn("sides=one-sided", source)
        self.assertIn("--dry-run", source)
        self.assertNotIn("printer-is-shared=true", source)
        endpoints = set(re.findall(r"(?:\d{1,3}\.){3}\d{1,3}", source))
        self.assertEqual(endpoints, {"127.0.0.1"})

    def test_desktop_launcher_is_file_aware_and_nonterminal(self):
        source = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn(
            "Exec=/data/data/com.termux/files/usr/local/bin/quest-inkscape-print %f",
            source,
        )
        self.assertIn("MimeType=image/svg+xml;", source)
        self.assertIn("Terminal=false", source)

    def test_smoke_fixture_contains_only_the_requested_minimal_marks(self):
        root = ET.parse(FIXTURE).getroot()
        local_names = [element.tag.rsplit("}", 1)[-1] for element in root.iter()]
        self.assertEqual(local_names.count("line"), 1)
        self.assertEqual(local_names.count("text"), 1)
        self.assertNotIn("rect", local_names)
        self.assertNotIn("path", local_names)
        text = "".join(root.itertext()).strip()
        self.assertEqual(text, "QTL")


if __name__ == "__main__":
    unittest.main()
