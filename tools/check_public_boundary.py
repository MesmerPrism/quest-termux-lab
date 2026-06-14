#!/usr/bin/env python3
"""Small public-boundary scanner for this repository."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


DENY_PATTERNS = [
    (re.compile(r"\b[A-Z]:\\", re.IGNORECASE), "Windows absolute path"),
    (re.compile(r"/home/[^/\s]+|/Users/[^/\s]+"), "user home path"),
    (re.compile(r"\b[A-Z0-9]{8,}H[0-9A-Z]{4,}\b"), "possible headset serial"),
    (re.compile(r"\bu0_a\d+\b"), "Android app UID from real device"),
    (re.compile(r"(?:token|secret|password)\s*[:=]", re.IGNORECASE), "possible credential assignment"),
    (re.compile(r"\badbkey(?:\.pub)?\b", re.IGNORECASE), "ADB key material reference"),
    (re.compile(r"Authorization:\s*Bearer\s+\S+", re.IGNORECASE), "HTTP bearer credential"),
    (re.compile(r"\bx-api-key\s*[:=]\s*\S+", re.IGNORECASE), "API key header or assignment"),
    (re.compile(r"\bclient_secret\s*[:=]\s*\S+", re.IGNORECASE), "client secret assignment"),
    (re.compile(r"\brefresh_token\s*[:=]\s*\S+", re.IGNORECASE), "refresh token assignment"),
    (re.compile(r"\btskey-auth-[A-Za-z0-9_-]+", re.IGNORECASE), "Tailscale auth key"),
    (re.compile(r"\btailscale\s+authkey\b", re.IGNORECASE), "Tailscale auth key label"),
    (re.compile(r"\bcloudflared\s+tunnel\s+token\b", re.IGNORECASE), "Cloudflare tunnel token label"),
    (re.compile(r"\btunnel_secret\s*[:=]\s*\S+", re.IGNORECASE), "Cloudflare tunnel secret assignment"),
    (re.compile(r"\bPrivateKey\s*=\s*[A-Za-z0-9+/=]{20,}"), "WireGuard private key"),
    (re.compile(r"\bhttps?://fleet\.[A-Za-z0-9.-]+\.(?:com|net|org|dev|io)\b", re.IGNORECASE), "possible real fleet controller domain"),
    (re.compile(r"\b(?:com\.viscereality|org\.mesmerprism\.study|io\.mesmerprism\.study)\.[A-Za-z0-9_.]+\b"), "possible private study package id"),
    (re.compile(r"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY"), "private key material"),
]
IPV4_PATTERN = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
SYNTHETIC_MARKER_REQUIRED = {
    "fleet-agent-config.synthetic.json",
    "fleet-agent-manifest.synthetic.json",
    "fleet-command-request.synthetic.json",
    "fleet-command-request.apk-update.synthetic.json",
    "fleet-command-request.uiautomator.synthetic.json",
    "fleet-command-request.uiautomator-system-surface.synthetic.json",
    "fleet-command-result.synthetic.json",
    "fleet-command-result.apk-update-recovery.synthetic.json",
    "remote-session-lease.synthetic.json",
}

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
FORBIDDEN_TRACKED_SUFFIXES = {
    ".apk",
    ".idsig",
    ".keystore",
    ".jks",
    ".p12",
    ".pfx",
    ".jar",
    ".aar",
    ".dex",
    ".so",
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

    try:
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        tracked = []

    for rel_text in tracked:
        rel = Path(rel_text)
        if rel.suffix.lower() in FORBIDDEN_TRACKED_SUFFIXES:
            findings.append(f"{rel}: forbidden tracked generated/binary artifact")

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
        if rel.parent.as_posix() == "examples" and rel.name in SYNTHETIC_MARKER_REQUIRED:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = None
            if not isinstance(payload, dict) or payload.get("synthetic") is not True:
                findings.append(f"{rel}: missing synthetic=true marker")

    if findings:
        print("public_boundary_failed")
        for finding in findings:
            print(finding)
        return 1

    print("public_boundary_ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
