#!/usr/bin/env python3
"""Recover a previously paired Android Wireless Debugging session from Termux."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Callable


STATUS_SCHEMA = "quest-termux-lab.wireless-adb-recovery-status.v1"
TLS_CONNECT_MDNS_SERVICE = "_adb-tls-connect._tcp"
DEFAULT_WORK_DIR = Path.home() / "quest-lab" / "wireless-adb-recovery"
DEFAULT_FLEET_DIR = Path.home() / "quest-lab" / "fleet-agent-live"
TERMUX_PREFIX_FALLBACK = Path("/data/data/com.termux/files/usr")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def termux_prefix() -> Path | None:
    configured = os.environ.get("PREFIX")
    if configured:
        return Path(configured)
    if TERMUX_PREFIX_FALLBACK.is_dir():
        return TERMUX_PREFIX_FALLBACK
    return None


def resolve_termux_executable(name: str) -> str:
    prefix = termux_prefix()
    candidate = prefix / "bin" / name if prefix else None
    return str(candidate) if candidate and candidate.is_file() else name


def adb_environment() -> dict[str, str]:
    env = os.environ.copy()
    prefix = termux_prefix()
    if prefix:
        env["PREFIX"] = str(prefix)
        env["PATH"] = os.pathsep.join((str(prefix / "bin"), env.get("PATH", "")))
    tmpdir = env.get("TMPDIR") or (str(prefix / "tmp") if prefix else None)
    if tmpdir:
        Path(tmpdir).mkdir(parents=True, exist_ok=True)
        env["TMPDIR"] = tmpdir
    return env


def run_adb(
    adb: str,
    args: list[str],
    timeout: float,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    return runner(
        [adb, *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
        env=adb_environment(),
    )


def bounded_command_result(result: subprocess.CompletedProcess[str], limit: int = 1024) -> dict[str, Any]:
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    return {
        "exit_code": result.returncode,
        "stdout": stdout[-limit:],
        "stderr": stderr[-limit:],
        "stdout_truncated": len(stdout) > limit,
        "stderr_truncated": len(stderr) > limit,
    }


def collect_safe_bootstrap_diagnostics(adb: str) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    for name, args in (
        ("adb_version", ["version"]),
        ("adb_mdns_check", ["mdns", "check"]),
        ("adb_mdns_services", ["mdns", "services"]),
    ):
        try:
            diagnostics[name] = bounded_command_result(run_adb(adb, args, 5.0))
        except (OSError, subprocess.TimeoutExpired) as failure:
            diagnostics[name] = {"error": type(failure).__name__}
    try:
        tls_property = subprocess.run(
            ["/system/bin/getprop", "service.adb.tls.port"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=3.0,
            check=False,
        )
        diagnostics["service_adb_tls_port"] = bounded_command_result(tls_property)
    except (OSError, subprocess.TimeoutExpired) as failure:
        diagnostics["service_adb_tls_port"] = {"error": type(failure).__name__}
    return diagnostics


def parse_tls_connect_targets(output: str, loopback_host: str = "127.0.0.1") -> list[str]:
    if loopback_host not in {"127.0.0.1", "localhost"}:
        raise ValueError("loopback_host must remain loopback")
    targets: list[str] = []
    for raw_line in output.splitlines():
        fields = raw_line.strip().split()
        if len(fields) < 3 or fields[-2] != TLS_CONNECT_MDNS_SERVICE:
            continue
        endpoint = fields[-1]
        if ":" not in endpoint:
            continue
        _, port_text = endpoint.rsplit(":", 1)
        try:
            port = int(port_text)
        except ValueError:
            continue
        if not 1 <= port <= 65535:
            continue
        target = f"{loopback_host}:{port}"
        if target not in targets:
            targets.append(target)
    return targets


def normalize_candidate_hosts(hosts: str | list[str]) -> list[str]:
    values = [hosts] if isinstance(hosts, str) else hosts
    normalized: list[str] = []
    for raw_host in values:
        try:
            address = ipaddress.ip_address(raw_host)
        except ValueError:
            continue
        if address.version != 4 or not (address.is_loopback or address.is_private):
            continue
        host = str(address)
        if host not in normalized:
            normalized.append(host)
    if "127.0.0.1" not in normalized:
        normalized.insert(0, "127.0.0.1")
    return normalized


def read_tls_port_property(
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> int | None:
    try:
        result = runner(
            ["/system/bin/getprop", "service.adb.tls.port"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=3.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    try:
        port = int(result.stdout.strip())
    except ValueError:
        return None
    return port if 1 <= port <= 65535 else None


def probe_tls_shell(
    adb: str,
    candidate_hosts: str | list[str],
    timeout: float,
    tls_port: int | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[str | None, str | None, str, bool]:
    hosts = normalize_candidate_hosts(candidate_hosts)
    if tls_port is not None:
        if not 1 <= tls_port <= 65535:
            return None, None, "invalid_tls_port", False
        targets = [f"{host}:{tls_port}" for host in hosts]
    else:
        mdns = run_adb(adb, ["mdns", "services"], timeout, runner)
        if mdns.returncode != 0:
            return None, None, "mdns_query_failed", False
        discovered_targets = parse_tls_connect_targets(mdns.stdout, "127.0.0.1")
        ports = []
        for target in discovered_targets:
            port = int(target.rsplit(":", 1)[1])
            if port not in ports:
                ports.append(port)
        if not ports:
            return None, None, "tls_mdns_service_not_found", False
        targets = [f"{host}:{port}" for port in ports for host in hosts]
    last_reason = "tls_connect_failed"
    for target in targets:
        run_adb(adb, ["connect", target], timeout, runner)
        ident = run_adb(adb, ["-s", target, "shell", "id"], timeout, runner)
        if ident.returncode == 0 and re.match(
            r"^uid=2000\(shell\)(?:\s|$)",
            ident.stdout,
        ):
            return target, "2000", "available", True
        if "failed to authenticate" in (ident.stdout + ident.stderr).lower():
            last_reason = "pairing_required"
        else:
            last_reason = "shell_uid_not_available"
    return None, None, last_reason, True


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def process_is_alive(pid_file: Path) -> bool:
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def start_fleet_agent(
    fleet_dir: Path = DEFAULT_FLEET_DIR,
    adb_target: str | None = None,
    popen: Callable[..., subprocess.Popen[Any]] = subprocess.Popen,
) -> dict[str, Any]:
    script = fleet_dir / "termux_fleet_agent.py"
    source_config = fleet_dir / "config.json"
    pid_file = fleet_dir / "agent-helper.pid"
    if not script.is_file() or not source_config.is_file():
        return {"state": "not_configured"}
    if process_is_alive(pid_file):
        return {"state": "already_running"}

    config = json.loads(source_config.read_text(encoding="utf-8"))
    config["local_adb_enabled"] = True
    config["local_adb_discovery"] = "tls_nsd" if adb_target else "tls_mdns"
    config["local_adb_loopback_host"] = "127.0.0.1"
    if adb_target:
        config["local_adb_target"] = adb_target
    config["check_local_adb_on_heartbeat"] = True
    runtime_config = fleet_dir / "config.tls-runtime.json"
    write_json_atomic(runtime_config, config)

    log_path = fleet_dir / "agent-helper.log"
    log_handle = log_path.open("ab")
    try:
        process = popen(
            [resolve_termux_executable("python"), str(script), "--config", str(runtime_config)],
            cwd=str(fleet_dir),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=adb_environment(),
        )
    finally:
        log_handle.close()
    pid_file.write_text(str(process.pid) + "\n", encoding="utf-8")
    return {"state": "started", "pid_recorded": True}


def wait_for_started_fleet_agent(
    fleet_result: dict[str, Any],
    fleet_dir: Path = DEFAULT_FLEET_DIR,
    waitpid: Callable[[int, int], tuple[int, int]] = os.waitpid,
) -> None:
    if fleet_result.get("state") != "started":
        return
    try:
        pid = int((fleet_dir / "agent-helper.pid").read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return
    while True:
        try:
            waitpid(pid, 0)
            return
        except InterruptedError:
            continue
        except (ChildProcessError, OSError):
            return


def recover(
    adb: str,
    loopback_host: str,
    tls_port: int | None,
    wait_seconds: float,
    poll_interval_seconds: float,
    status_path: Path,
    start_agent: bool,
    candidate_hosts: list[str] | None = None,
    topology_mode: str = "none",
    port_source: str = "android_nsd",
    include_safe_diagnostics: bool = False,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    started = monotonic()
    run_adb(adb, ["start-server"], min(10.0, max(1.0, wait_seconds)), runner)
    target = None
    shell_uid = None
    reason = "tls_mdns_service_not_found"
    hosts = normalize_candidate_hosts(candidate_hosts or [loopback_host])
    service_discovered = tls_port is not None
    effective_port_source = port_source if tls_port is not None else "none"
    attempts = 0
    while True:
        attempts += 1
        try:
            effective_tls_port = tls_port
            if effective_tls_port is None:
                effective_tls_port = read_tls_port_property()
                if effective_tls_port is not None:
                    effective_port_source = "system_property"
            target, shell_uid, reason, discovered = probe_tls_shell(
                adb,
                hosts,
                8.0,
                effective_tls_port,
                runner,
            )
            service_discovered = service_discovered or discovered
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            reason = type(exc).__name__
        if target and shell_uid == "2000":
            break
        if monotonic() - started >= wait_seconds:
            break
        sleeper(max(0.1, poll_interval_seconds))

    available = target is not None and shell_uid == "2000"
    fleet_result = start_fleet_agent(adb_target=target) if available and start_agent else {"state": "not_requested"}
    if effective_port_source == "system_property":
        discovery_mode = "tls_property"
    else:
        discovery_mode = "tls_nsd" if tls_port is not None else "tls_mdns"
    payload = {
        "schema": STATUS_SCHEMA,
        "observed_at": utc_now(),
        "state": "available" if available else "unavailable",
        "attempt_count": attempts,
        "discovery_mode": discovery_mode,
        "tls_service_discovered": service_discovered,
        "requested_tls_port": tls_port,
        "tls_port_source": effective_port_source,
        "topology_mode": topology_mode,
        "candidate_hosts": hosts,
        "local_adb": {
            "available": available,
            "target": target,
            "shell_uid": shell_uid,
            "reason": None if available else reason,
        },
        "fleet_agent": fleet_result,
    }
    if include_safe_diagnostics:
        payload["safe_bootstrap_diagnostics"] = collect_safe_bootstrap_diagnostics(adb)
    write_json_atomic(status_path, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adb", default=resolve_termux_executable("adb"))
    parser.add_argument("--loopback-host", default="127.0.0.1")
    parser.add_argument("--candidate-host", action="append", default=[])
    parser.add_argument("--tls-port", type=int)
    parser.add_argument("--port-source", default="android_nsd")
    parser.add_argument("--topology-mode", default="none")
    parser.add_argument("--wait-seconds", type=float, default=120.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    parser.add_argument("--status", type=Path, default=DEFAULT_WORK_DIR / "status.json")
    parser.add_argument("--no-start-fleet-agent", action="store_true")
    parser.add_argument("--hold-fleet-agent", action="store_true")
    parser.add_argument("--safe-bootstrap-diagnostics", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = recover(
        adb=args.adb,
        loopback_host=args.loopback_host,
        tls_port=args.tls_port,
        wait_seconds=max(0.0, args.wait_seconds),
        poll_interval_seconds=max(0.1, args.poll_interval_seconds),
        status_path=args.status,
        start_agent=not args.no_start_fleet_agent,
        candidate_hosts=args.candidate_host or [args.loopback_host],
        topology_mode=args.topology_mode,
        port_source=args.port_source,
        include_safe_diagnostics=args.safe_bootstrap_diagnostics,
    )
    print(json.dumps(payload, separators=(",", ":")), flush=True)
    if args.hold_fleet_agent:
        wait_for_started_fleet_agent(payload["fleet_agent"])
    return 0 if payload["local_adb"]["available"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
