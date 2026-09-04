#!/usr/bin/env python3
"""Validate tracked JSON data and local inline Markdown links."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote


INLINE_LINK = re.compile(r"!?\[[^\]]*\]\((?P<target><[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)")
EXTERNAL_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def tracked_paths(root: Path) -> list[Path]:
    try:
        output = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
    except OSError as exc:
        raise RuntimeError(f"cannot execute git: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or "git ls-files failed"
        raise RuntimeError(detail) from exc
    return [Path(value) for value in output.split("\0") if value]


def check_json(path: Path, rel: Path, findings: list[str]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        findings.append(f"{rel}: cannot read UTF-8 JSON: {exc}")
        return

    if rel.suffix.lower() == ".jsonl":
        for line_no, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                findings.append(f"{rel}:{line_no}: invalid JSONL: {exc.msg}")
        return

    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        findings.append(f"{rel}:{exc.lineno}: invalid JSON: {exc.msg}")


def check_markdown(root: Path, path: Path, rel: Path, findings: list[str]) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        findings.append(f"{rel}: cannot read UTF-8 Markdown: {exc}")
        return

    for line_no, line in enumerate(lines, start=1):
        for match in INLINE_LINK.finditer(line):
            target = match.group("target").strip("<>")
            if not target or target.startswith(("#", "/")) or EXTERNAL_SCHEME.match(target):
                continue
            target = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not target:
                continue
            candidate = (path.parent / Path(target)).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                findings.append(f"{rel}:{line_no}: relative link escapes repository root: {target}")
                continue
            if not candidate.exists():
                findings.append(f"{rel}:{line_no}: missing relative link target: {target}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="repository root")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    findings: list[str] = []
    try:
        paths = tracked_paths(root)
    except RuntimeError as exc:
        print("repository_integrity_failed")
        print(f"git inventory unavailable: {exc}")
        return 1

    for rel in paths:
        path = root / rel
        suffix = rel.suffix.lower()
        if suffix in {".json", ".jsonl"}:
            check_json(path, rel, findings)
        elif suffix == ".md":
            check_markdown(root, path, rel, findings)

    if findings:
        print("repository_integrity_failed")
        for finding in findings:
            print(finding)
        return 1

    print("repository_integrity_ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
