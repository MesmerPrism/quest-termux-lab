#!/usr/bin/env python3
"""Small public-boundary scanner for this repository."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


DENY_PATTERNS = [
    (re.compile(r"\b[A-Z]:\\", re.IGNORECASE), "Windows absolute path"),
    (re.compile(r"/home/[^/\s]+|/Users/[^/\s]+"), "user home path"),
    (re.compile(r"\b[A-Z0-9]{8,}H[0-9A-Z]{4,}\b"), "possible headset serial"),
    (re.compile(r"\bu0_a\d+\b"), "Android app UID from real device"),
    (re.compile(r"(?:token|secret|password)\s*[:=]", re.IGNORECASE), "possible credential assignment"),
    (re.compile(r"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY"), "private key material"),
]
IPV4_PATTERN = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")

SKIP_DIRS = {".git", "__pycache__", "runs", "artifacts", "captures", "logs"}
TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".jsonl",
    ".py",
    ".java",
    ".ps1",
    ".sh",
    ".toml",
    ".xml",
    ".yml",
    ".yaml",
    ".gitignore",
    ".patch",
    ".diff",
}


def should_scan(path: Path) -> bool:
    if path.as_posix() == "tools/check_public_boundary.py":
        return False
    if any(part in SKIP_DIRS for part in path.parts):
        return False
    if path.name in {"LICENSE", ".gitignore"}:
        return True
    return path.suffix.lower() in TEXT_SUFFIXES


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="repository root")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    findings: list[str] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file() or not should_scan(path.relative_to(root)):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(root)
        for line_no, line in enumerate(text.splitlines(), start=1):
            for pattern, label in DENY_PATTERNS:
                if pattern.search(line):
                    findings.append(f"{rel}:{line_no}: {label}")
            for match in IPV4_PATTERN.finditer(line):
                value = match.group(0)
                if value not in {"127.0.0.1", "0.0.0.0"}:
                    findings.append(f"{rel}:{line_no}: raw non-loopback IPv4 address")

    if findings:
        print("public_boundary_failed")
        for finding in findings:
            print(finding)
        return 1

    print("public_boundary_ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
