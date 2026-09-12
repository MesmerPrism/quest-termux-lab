#!/usr/bin/env python3
"""Tests for the Termux TLS Wireless Debugging recovery payload."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ElementTree


REPO_ROOT = Path(__file__).resolve().parents[1]
RECOVERY_PATH = REPO_ROOT / "examples" / "wireless-adb-recovery-helper" / "assets" / "wireless_adb_recovery.py"
HEARTBEAT_WAITER_PATH = REPO_ROOT / "tools" / "wait_for_tls_recovery_heartbeat.py"


def load_recovery_module():
    spec = importlib.util.spec_from_file_location("wireless_adb_recovery", RECOVERY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load wireless ADB recovery module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_heartbeat_waiter_module():
    spec = importlib.util.spec_from_file_location("wait_for_tls_recovery_heartbeat", HEARTBEAT_WAITER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load heartbeat waiter module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class WirelessAdbRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.recovery = load_recovery_module()
        self.waiter = load_heartbeat_waiter_module()

    def completed(self, stdout: str = "", stderr: str = "", code: int = 0):
        return subprocess.CompletedProcess([], code, stdout=stdout, stderr=stderr)

    def test_parses_only_tls_connect_service_and_rewrites_to_loopback(self) -> None:
        output = """List of discovered mdns services
adb-example _adb-tls-connect._tcp quest-device.local:38471
adb-pair _adb-tls-pairing._tcp quest-device.local:41234
adb-classic _adb._tcp quest-device.local:5555
"""
        self.assertEqual(
            self.recovery.parse_tls_connect_targets(output),
            ["127.0.0.1:38471"],
        )

    def test_helper_manifest_keeps_recovery_authority_out_of_termux_and_the_hub(self) -> None:
        manifest_path = RECOVERY_PATH.parents[1] / "AndroidManifest.xml"
        root = ElementTree.parse(manifest_path).getroot()
        android = "{http://schemas.android.com/apk/res/android}"
        permissions = {
            node.attrib[android + "name"]
            for node in root.findall("uses-permission")
        }
        self.assertIn("android.permission.WRITE_SECURE_SETTINGS", permissions)
        self.assertIn("android.permission.RECEIVE_BOOT_COMPLETED", permissions)
        self.assertIn("com.termux.permission.RUN_COMMAND", permissions)
        self.assertIn("android.permission.INTERNET", permissions)
        self.assertIn("android.permission.NEARBY_WIFI_DEVICES", permissions)
        self.assertIn("android.permission.CHANGE_WIFI_STATE", permissions)
        self.assertIn("android.permission.FOREGROUND_SERVICE_CONNECTED_DEVICE", permissions)
        self.assertIn(
            "org.questtermuxlab.wirelessadbrecovery.permission.READ_LOOPBACK_ADB_PROOF",
            permissions,
        )
        self.assertNotIn("android.permission.QUERY_ALL_PACKAGES", permissions)
        categories = {
            node.attrib[android + "name"]
            for node in root.findall(".//category")
        }
        self.assertNotIn("android.intent.category.HOME", categories)
        declared = root.find("permission")
        self.assertIsNotNone(declared)
        self.assertEqual(
            declared.attrib[android + "name"],
            "org.questtermuxlab.wirelessadbrecovery.permission.READ_LOOPBACK_ADB_PROOF",
        )
        self.assertEqual(declared.attrib[android + "protectionLevel"], "signature")
        provider = root.find("./application/provider")
        self.assertIsNotNone(provider)
        self.assertEqual(
            provider.attrib[android + "authorities"],
            "org.questtermuxlab.wirelessadbrecovery.loopbackproof",
        )
        self.assertEqual(provider.attrib[android + "exported"], "true")
        self.assertEqual(provider.attrib[android + "grantUriPermissions"], "false")
        self.assertEqual(
            provider.attrib[android + "readPermission"],
            "org.questtermuxlab.wirelessadbrecovery.permission.READ_LOOPBACK_ADB_PROOF",
        )

    def test_loopback_proof_provider_is_query_only_and_sanitized(self) -> None:
        source_root = (
            RECOVERY_PATH.parents[1]
            / "src"
            / "org"
            / "questtermuxlab"
            / "wirelessadbrecovery"
        )
        provider = (source_root / "LoopbackAdbProofProvider.java").read_text(
            encoding="utf-8"
        )
        for column in (
            "schema",
            "evidence_revision",
            "observed_at_ms",
            "fresh_until_ms",
            "state",
            "route_mode",
            "discovery_mode",
            "listener_discovered",
            "shell_uid",
            "owner_evidence_sha256",
        ):
            self.assertIn(f'"{column}"', provider)
        for forbidden in (
            '"endpoint"',
            '"host"',
            '"port"',
            '"serial"',
            '"stdout"',
            '"filesystem_path"',
            '"operation_id"',
            '"preview_id"',
        ):
            self.assertNotIn(forbidden, provider)
        self.assertIn('throw new UnsupportedOperationException("query_only")', provider)
        self.assertIn('!"tls_shell_available".equals(state)', provider)
        self.assertIn('!"2000".equals(shellUid)', provider)
        self.assertIn("MAX_PROOF_LIFETIME_MS = 60_000L", provider)
        result_service = (source_root / "RecoveryResultService.java").read_text(
            encoding="utf-8"
        )
        self.assertIn("KEY_EVIDENCE_REVISION", result_service)
        self.assertIn("computeOwnerEvidenceSha256", result_service)
        self.assertIn(".commit()", result_service)

    def test_helper_uses_android_nsd_and_limits_fallbacks_to_local_candidates(self) -> None:
        source = (RECOVERY_PATH.parents[1] / "src" / "org" / "questtermuxlab"
                  / "wirelessadbrecovery" / "RecoveryService.java").read_text(encoding="utf-8")
        self.assertIn("NsdManager", source)
        self.assertIn("_adb-tls-connect._tcp.", source)
        self.assertIn('" --tls-port " + tlsPort', source)
        self.assertIn('" --candidate-host \\""', source)
        self.assertNotIn("--candidate-network", source)

    def test_topology_probe_is_bounded_and_cleans_both_android_topologies(self) -> None:
        source_root = RECOVERY_PATH.parents[1] / "src" / "org" / "questtermuxlab" / "wirelessadbrecovery"
        source = (source_root / "TopologyProbeService.java").read_text(encoding="utf-8")
        self.assertIn("WifiP2pManager", source)
        self.assertIn("createGroup", source)
        self.assertIn("startLocalOnlyHotspot", source)
        self.assertIn("LocalOnlyHotspotReservation", source)
        self.assertIn("MAX_HOLD_MS = 240_000L", source)
        self.assertIn("removeGroup", source)
        self.assertIn("hotspotReservation.close()", source)
        self.assertIn('active ? addresses.interfaces : "none"', source)
        activity = (source_root / "MainActivity.java").read_text(encoding="utf-8")
        self.assertIn("String topologyInterfaces = topologyActive", activity)

    def test_pairing_is_operator_coded_and_sent_to_termux_stdin(self) -> None:
        source_root = RECOVERY_PATH.parents[1] / "src" / "org" / "questtermuxlab" / "wirelessadbrecovery"
        service = (source_root / "RecoveryService.java").read_text(encoding="utf-8")
        activity = (source_root / "MainActivity.java").read_text(encoding="utf-8")
        self.assertIn("_adb-tls-pairing._tcp.", service)
        self.assertIn('dispatchTermuxCommand(command, pairingCode + "\\n", "pair")', service)
        self.assertNotIn("adb pair 127.0.0.1:" + '" + pairingPort + " " + pairingCode', service)
        self.assertIn("android.settings.WIRELESS_DEBUGGING_SETTINGS", activity)
        self.assertIn('code.matches("\\\\d{6}")', activity)

    def test_post_reboot_waiter_requires_fresh_sequence_reset_and_uid_gate(self) -> None:
        not_before = self.waiter.parse_timestamp("2026-07-14T23:52:01Z")
        heartbeat = {
            "sequence": 1,
            "observed_at": "2026-07-15T00:01:02Z",
            "local_adb": {
                "checked": True,
                "available": True,
                "discovery_mode": "tls_nsd",
                "tls_service_discovered": True,
                "shell_uid": "2000",
            },
        }
        self.assertTrue(self.waiter.proves_post_reboot_recovery(heartbeat, 72, not_before))
        heartbeat["sequence"] = 73
        self.assertFalse(self.waiter.proves_post_reboot_recovery(heartbeat, 72, not_before))

    def test_probe_requires_shell_uid_2000(self) -> None:
        responses = [
            self.completed("adb-example _adb-tls-connect._tcp quest-device.local:38471\n"),
            self.completed("connected\n"),
            self.completed("uid=2000(shell) gid=2000(shell)\n"),
        ]
        runner = mock.Mock(side_effect=responses)
        target, uid, reason, discovered = self.recovery.probe_tls_shell("adb", "127.0.0.1", 5.0, None, runner)
        self.assertEqual((target, uid, reason), ("127.0.0.1:38471", "2000", "available"))
        self.assertTrue(discovered)
        self.assertEqual(runner.call_args_list[1].args[0], ["adb", "connect", "127.0.0.1:38471"])

    def test_probe_rejects_uid_substrings_and_non_shell_identity(self) -> None:
        for identity in (
            "uid=20000(shell) gid=20000(shell)\n",
            "xuid=2000(shell) gid=2000(shell)\n",
            "uid=2000(other) gid=2000(other)\n",
            "prefix uid=2000(shell) gid=2000(shell)\n",
        ):
            with self.subTest(identity=identity):
                responses = [
                    self.completed(
                        "adb-example _adb-tls-connect._tcp "
                        "quest-device.local:38471\n"
                    ),
                    self.completed("connected\n"),
                    self.completed(identity),
                ]
                target, uid, reason, discovered = self.recovery.probe_tls_shell(
                    "adb",
                    "127.0.0.1",
                    5.0,
                    None,
                    mock.Mock(side_effect=responses),
                )
                self.assertEqual((target, uid, reason), (None, None, "shell_uid_not_available"))
                self.assertTrue(discovered)

    def test_android_nsd_port_bypasses_unsupported_adb_mdns_service(self) -> None:
        responses = [
            self.completed("connected\n"),
            self.completed("uid=2000(shell) gid=2000(shell)\n"),
        ]
        runner = mock.Mock(side_effect=responses)
        target, uid, reason, discovered = self.recovery.probe_tls_shell(
            "adb", "127.0.0.1", 5.0, 38471, runner
        )
        self.assertEqual((target, uid, reason), ("127.0.0.1:38471", "2000", "available"))
        self.assertTrue(discovered)
        self.assertEqual(runner.call_args_list[0].args[0], ["adb", "connect", "127.0.0.1:38471"])

    def test_explicit_tls_port_probes_only_local_interface_candidates(self) -> None:
        p2p_host = "192.168." + "49.1"
        public_host = "8.8." + "8.8"
        responses = [
            self.completed("unable to connect\n", code=1),
            self.completed("not found\n", code=1),
            self.completed("connected\n"),
            self.completed("uid=2000(shell) gid=2000(shell)\n"),
        ]
        runner = mock.Mock(side_effect=responses)
        target, uid, reason, discovered = self.recovery.probe_tls_shell(
            "adb",
            [p2p_host, public_host],
            5.0,
            38471,
            runner,
        )
        self.assertEqual((target, uid, reason), (f"{p2p_host}:38471", "2000", "available"))
        self.assertTrue(discovered)
        attempted = [call.args[0][-1] for call in runner.call_args_list if call.args[0][1] in {"connect", "-s"}]
        self.assertNotIn(f"{public_host}:38471", attempted)

    def test_self_hosted_recovery_uses_readable_tls_property_when_mdns_is_absent(self) -> None:
        hotspot_host = "192.168." + "43.1"
        responses = [
            self.completed(),
            self.completed("connected\n"),
            self.completed("uid=2000(shell) gid=2000(shell)\n"),
        ]
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            self.recovery, "read_tls_port_property", return_value=38471
        ):
            payload = self.recovery.recover(
                adb="adb",
                loopback_host="127.0.0.1",
                tls_port=None,
                wait_seconds=0,
                poll_interval_seconds=0.1,
                status_path=Path(tmp) / "status.json",
                start_agent=False,
                candidate_hosts=["127.0.0.1", hotspot_host],
                topology_mode="local_only_hotspot_owner",
                runner=mock.Mock(side_effect=responses),
            )
        self.assertTrue(payload["local_adb"]["available"])
        self.assertEqual(payload["local_adb"]["target"], "127.0.0.1:38471")
        self.assertEqual(payload["local_adb"]["shell_uid"], "2000")
        self.assertEqual(payload["discovery_mode"], "tls_property")
        self.assertIsNone(payload["requested_tls_port"])
        self.assertEqual(payload["tls_port_source"], "system_property")
        self.assertEqual(payload["topology_mode"], "local_only_hotspot_owner")

    def test_resolves_noninteractive_termux_executables_from_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp)
            (prefix / "bin").mkdir()
            adb = prefix / "bin" / "adb"
            python = prefix / "bin" / "python"
            adb.touch()
            python.touch()
            with mock.patch.dict(self.recovery.os.environ, {"PREFIX": str(prefix)}, clear=True):
                self.assertEqual(self.recovery.resolve_termux_executable("adb"), str(adb))
                self.assertEqual(self.recovery.resolve_termux_executable("python"), str(python))
                environment = self.recovery.adb_environment()
        self.assertEqual(environment["PREFIX"], str(prefix))
        self.assertEqual(environment["PATH"].split(self.recovery.os.pathsep)[0], str(prefix / "bin"))

    def test_recovery_does_not_fall_back_to_classic_5555(self) -> None:
        responses = [
            self.completed(),
            self.completed("adb-classic _adb._tcp quest-device.local:5555\n"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            payload = self.recovery.recover(
                adb="adb",
                loopback_host="127.0.0.1",
                tls_port=None,
                wait_seconds=0,
                poll_interval_seconds=0.1,
                status_path=Path(tmp) / "status.json",
                start_agent=False,
                runner=mock.Mock(side_effect=responses),
            )
        self.assertFalse(payload["local_adb"]["available"])
        self.assertEqual(payload["local_adb"]["reason"], "tls_mdns_service_not_found")

    def test_fleet_runtime_config_enables_tls_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fleet_dir = Path(tmp)
            (fleet_dir / "termux_fleet_agent.py").write_text("print('agent')\n", encoding="utf-8")
            (fleet_dir / "config.json").write_text(
                json.dumps({"local_adb_enabled": False, "local_adb_target": "127.0.0.1:5555"}),
                encoding="utf-8",
            )
            process = mock.Mock(pid=1234)
            popen = mock.Mock(return_value=process)
            with mock.patch.object(self.recovery, "process_is_alive", return_value=False):
                result = self.recovery.start_fleet_agent(
                    fleet_dir=fleet_dir,
                    adb_target="127.0.0.1:38471",
                    popen=popen,
                )
            runtime = json.loads((fleet_dir / "config.tls-runtime.json").read_text(encoding="utf-8"))
        self.assertEqual(result["state"], "started")
        self.assertTrue(runtime["local_adb_enabled"])
        self.assertEqual(runtime["local_adb_discovery"], "tls_nsd")
        self.assertEqual(runtime["local_adb_target"], "127.0.0.1:38471")
        self.assertEqual(runtime["local_adb_loopback_host"], "127.0.0.1")
        self.assertTrue(runtime["check_local_adb_on_heartbeat"])

    def test_hold_waits_for_started_fleet_agent_pid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fleet_dir = Path(tmp)
            (fleet_dir / "agent-helper.pid").write_text("1234\n", encoding="utf-8")
            waitpid = mock.Mock(return_value=(1234, 0))
            self.recovery.wait_for_started_fleet_agent(
                {"state": "started"},
                fleet_dir=fleet_dir,
                waitpid=waitpid,
            )
        waitpid.assert_called_once_with(1234, 0)


if __name__ == "__main__":
    unittest.main()
