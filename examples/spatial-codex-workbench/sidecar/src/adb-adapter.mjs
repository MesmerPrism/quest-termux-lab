import { timingSafeEqual } from "node:crypto";
import { WorkbenchError, requireValue } from "./errors.mjs";
import { boundedString, operationId, redactText, sha256File } from "./util.mjs";

const TARGET_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/;

export class AdbAdapter {
  constructor({ tools, runner, journal, builds }) {
    this.tools = tools;
    this.runner = runner;
    this.journal = journal;
    this.builds = builds;
  }

  async targets() {
    const result = await this.runner.run(this.tools.adb, ["devices", "-l"], { timeoutMs: 15000, maxOutputBytes: 256 * 1024 });
    return result.stdout.split(/\r?\n/).slice(1).map((line) => line.trim()).filter(Boolean).map((line) => {
      const [target, state, ...details] = line.split(/\s+/);
      return { target, state, details: redactText(details.join(" "), 256) };
    }).filter((entry) => TARGET_PATTERN.test(entry.target));
  }

  validateTarget(target) {
    requireValue(typeof target === "string" && TARGET_PATTERN.test(target), "invalid_adb_target", "ADB target is invalid.");
    return target;
  }

  async requireShell(target) {
    this.validateTarget(target);
    const result = await this.runner.run(this.tools.adb, ["-s", target, "shell", "id"], { timeoutMs: 15000, maxOutputBytes: 65536 });
    requireValue(/\buid=2000\(shell\)/.test(result.stdout), "adb_shell_lease_missing", "Selected ADB target does not have Android shell authority.", 409);
    return true;
  }

  async install({ target, buildId, allowDowngrade = false }) {
    target = this.validateTarget(target);
    requireValue(allowDowngrade === false, "downgrade_not_supported", "Version 0.1 does not enable downgrade installs.", 409);
    const build = this.builds.requireCompleted(buildId);
    await this.requireShell(target);
    const currentHash = await sha256File(build.artifact_path);
    const expected = Buffer.from(build.artifact.apk_sha256, "hex");
    const current = Buffer.from(currentHash, "hex");
    requireValue(expected.length === current.length && timingSafeEqual(expected, current), "artifact_hash_mismatch", "APK changed after build confirmation.", 409);
    const id = operationId("install");
    this.journal.append({ operationId: id, runId: build.run_id, kind: "deploy.install_started", status: "running", summary: "APK installation started on the selected target." });
    try {
      const result = await this.runner.run(this.tools.adb, ["-s", target, "install", "-r", "-g", build.artifact_path], { timeoutMs: 5 * 60 * 1000, maxOutputBytes: 1024 * 1024 });
      requireValue(/Success/i.test(result.stdout + result.stderr), "install_not_confirmed", "ADB did not report installation success.", 502);
      this.journal.append({ operationId: id, runId: build.run_id, kind: "deploy.installed", status: "pass", summary: "APK installed on the selected target." });
      return { operation_id: id, status: "installed", build_id: buildId, package: build.artifact.package, version_name: build.artifact.version_name };
    } catch (error) {
      this.journal.append({ operationId: id, runId: build.run_id, kind: "deploy.install_failed", status: "fail", summary: "APK installation failed." });
      throw new WorkbenchError("install_failed", redactText(error.message, 512), 502);
    }
  }

  async launch({ target, buildId }) {
    target = this.validateTarget(target);
    const build = this.builds.requireCompleted(buildId);
    await this.requireShell(target);
    const component = `${build.artifact.package}/${build.artifact.activity}`;
    boundedString(component, "Launch component", 256);
    const id = operationId("launch");
    this.journal.append({ operationId: id, runId: build.run_id, kind: "deploy.launch_started", status: "running", summary: "APK launch started on the selected target." });
    try {
      const launch = await this.runner.run(this.tools.adb, ["-s", target, "shell", "am", "start", "-W", "-n", component], { timeoutMs: 60000, maxOutputBytes: 512 * 1024 });
      requireValue(/Status:\s*ok/i.test(launch.stdout) || /Starting:/i.test(launch.stdout), "launch_not_confirmed", "Activity manager did not confirm launch.", 502);
      const pid = await this.runner.run(this.tools.adb, ["-s", target, "shell", "pidof", build.artifact.package], { timeoutMs: 15000, maxOutputBytes: 65536 });
      requireValue(/^\s*[0-9]+(?:\s+[0-9]+)*\s*$/.test(pid.stdout), "process_not_running", "Launched package has no running process.", 502);
      const logs = await this.runner.run(this.tools.adb, ["-s", target, "logcat", "-d", "-t", "250"], { timeoutMs: 30000, maxOutputBytes: 2 * 1024 * 1024 });
      const fatal = logs.stdout.split(/\r?\n/).filter((line) => line.includes(build.artifact.package) && /FATAL EXCEPTION|AndroidRuntime/.test(line));
      requireValue(fatal.length === 0, "bounded_fatal", "A bounded package fatal was detected after launch.", 502);
      this.journal.append({ operationId: id, runId: build.run_id, kind: "deploy.launched", status: "pass", summary: "APK launched and its process is running without a bounded package fatal." });
      return { operation_id: id, status: "launched", build_id: buildId, package: build.artifact.package, version_name: build.artifact.version_name, fatal_count: 0 };
    } catch (error) {
      this.journal.append({ operationId: id, runId: build.run_id, kind: "deploy.launch_failed", status: "fail", summary: "APK launch verification failed." });
      throw new WorkbenchError("launch_failed", redactText(error.message, 512), 502);
    }
  }
}
