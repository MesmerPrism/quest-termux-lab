#!/usr/bin/env python3
"""Wait for strict post-reboot TLS shell evidence in a fleet heartbeat log."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any


def parse_timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_latest(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            if size == 0:
                return None
            position = size - 1
            while position > 0:
                handle.seek(position)
                if handle.read(1) == b"\n" and position < size - 1:
                    break
                position -= 1
            if position > 0:
                position += 1
            handle.seek(position)
            line = handle.readline().decode("utf-8").strip()
    except FileNotFoundError:
        return None
    if not line:
        return None
    payload = json.loads(line)
    return payload if isinstance(payload, dict) else None


def proves_post_reboot_recovery(
    heartbeat: dict[str, Any],
    pre_reboot_sequence: int,
    not_before: datetime,
) -> bool:
    try:
        observed = parse_timestamp(str(heartbeat["observed_at"]))
        sequence = int(heartbeat["sequence"])
        local_adb = heartbeat["local_adb"]
    except (KeyError, TypeError, ValueError):
        return False
    return (
        observed > not_before
        and sequence < pre_reboot_sequence
        and isinstance(local_adb, dict)
        and local_adb.get("checked") is True
        and local_adb.get("available") is True
        and local_adb.get("discovery_mode") == "tls_nsd"
        and local_adb.get("tls_service_discovered") is True
        and str(local_adb.get("shell_uid")) == "2000"
    )


def summary(heartbeat: dict[str, Any] | None) -> str:
    if heartbeat is None:
        return "heartbeat=missing"
    local_adb = heartbeat.get("local_adb") if isinstance(heartbeat.get("local_adb"), dict) else {}
    return (
        f"sequence={heartbeat.get('sequence')} observed_at={heartbeat.get('observed_at')} "
        f"available={local_adb.get('available')} discovery={local_adb.get('discovery_mode')} "
        f"shell_uid={local_adb.get('shell_uid')}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("heartbeat_log", type=Path)
    parser.add_argument("--pre-reboot-sequence", type=int, required=True)
    parser.add_argument("--not-before", type=parse_timestamp, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=480.0)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    args = parser.parse_args()

    deadline = time.monotonic() + max(0.0, args.timeout_seconds)
    last_summary = None
    while True:
        heartbeat = read_latest(args.heartbeat_log)
        current_summary = summary(heartbeat)
        if current_summary != last_summary:
            print(current_summary, flush=True)
            last_summary = current_summary
        if heartbeat and proves_post_reboot_recovery(
            heartbeat,
            args.pre_reboot_sequence,
            args.not_before,
        ):
            print("post_reboot_tls_recovery_proved", flush=True)
            return 0
        if time.monotonic() >= deadline:
            print("post_reboot_tls_recovery_timeout", flush=True)
            return 2
        time.sleep(max(0.1, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
