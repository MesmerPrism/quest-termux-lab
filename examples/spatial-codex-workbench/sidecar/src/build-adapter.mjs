import { mkdir, readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { WorkbenchError, requireValue } from "./errors.mjs";
import { operationId, redactText, sha256File } from "./util.mjs";

export function formatBuildFailure(error) {
  const stderr = typeof error?.result?.stderr === "string" ? error.result.stderr.trim() : "";
  const tail = stderr.split(/\r?\n/).filter(Boolean).slice(-8).join(" ");
  const prefix = redactText(error.message, 96);
  const detail = redactText(tail, 2048);
  return detail ? `${prefix} ${detail.slice(-Math.max(0, 511 - prefix.length))}` : prefix;
}

export class BuildAdapter {
  constructor({ tools, runner, journal, workspace, androidJar, keystorePath }) {
    this.tools = tools;
    this.runner = runner;
    this.journal = journal;
    this.workspace = workspace;
    this.androidJar = androidJar;
    this.keystorePath = keystorePath;
    this.builds = new Map();
    this.activeId = null;
  }

  async start(kind) {
    requireValue(kind === "preview" || kind === "candidate", "invalid_build_kind", "Build kind must be preview or candidate.");
    requireValue(this.activeId === null, "build_busy", "A build is already active.", 409);
    const cwd = this.workspace.requireRun();
    const source = await this.workspace.status();
    if (kind === "candidate") requireValue(source.clean, "candidate_requires_clean_source", "Candidate builds require a clean committed worktree.", 409);
    requireValue(this.androidJar, "android_jar_missing", "ANDROID_JAR is not configured.", 409);
    const id = operationId("build");
    const outDir = path.join(this.workspace.artifactsRoot, this.workspace.current.runId, id);
    const record = {
      id,
      run_id: this.workspace.current.runId,
      kind,
      status: "running",
      source_commit: source.head,
      source_clean: source.clean,
      artifact: null,
      artifact_path: null,
      error: null,
      started_at: new Date().toISOString(),
      completed_at: null,
      controller: new AbortController(),
    };
    this.builds.set(id, record);
    this.activeId = id;
    this.journal.append({ operationId: id, runId: record.run_id, kind: "build.started", status: "running", summary: `${kind} APK build started.` });
    this.execute(record, cwd, outDir).catch(() => {});
    return this.publicRecord(record);
  }

  async execute(record, cwd, outDir) {
    try {
      await stat(this.androidJar);
      await mkdir(path.dirname(outDir), { recursive: true });
      const script = path.join(cwd, "build.sh");
      const result = await this.runner.run(this.tools.shell, [script], {
        cwd,
        env: {
          OUT_DIR: outDir,
          ANDROID_JAR: this.androidJar,
          KEYSTORE_PATH: this.keystorePath,
        },
        timeoutMs: 20 * 60 * 1000,
        maxOutputBytes: 8 * 1024 * 1024,
        signal: record.controller.signal,
      });
      const artifactPath = result.stdout.trim().split(/\r?\n/).filter(Boolean).pop();
      requireValue(artifactPath && path.resolve(artifactPath).startsWith(path.resolve(outDir) + path.sep), "artifact_path_invalid", "Build returned an artifact outside its output directory.", 500);
      const metadataPath = path.join(outDir, "artifact-metadata.json");
      const metadata = JSON.parse(await readFile(metadataPath, "utf8"));
      const actualHash = await sha256File(artifactPath);
      requireValue(metadata.apk_sha256 === actualHash, "artifact_hash_mismatch", "Built APK hash does not match its metadata.", 500);
      record.artifact_path = artifactPath;
      record.artifact = metadata;
      record.status = "completed";
      await writeFile(path.join(outDir, "run-capsule.private.json"), JSON.stringify({
        schema: "quest-termux-lab.spatial-codex-workbench-run-capsule.private.v1",
        build_id: record.id,
        run_id: record.run_id,
        kind: record.kind,
        source_commit: record.source_commit,
        source_clean: record.source_clean,
        artifact: metadata,
      }, null, 2) + "\n", "utf8");
      this.journal.append({ operationId: record.id, runId: record.run_id, kind: "build.completed", status: "pass", summary: `${record.kind} APK built and verified.` });
    } catch (error) {
      const canceled = error.code === "canceled";
      record.status = canceled ? "canceled" : "failed";
      record.error = { code: error.code ?? "build_failed", message: formatBuildFailure(error) };
      this.journal.append({ operationId: record.id, runId: record.run_id, kind: canceled ? "build.canceled" : "build.failed", status: canceled ? "canceled" : "fail", summary: canceled ? "APK build canceled." : "APK build failed." });
    } finally {
      record.completed_at = new Date().toISOString();
      record.controller = null;
      if (this.activeId === record.id) this.activeId = null;
    }
  }

  get(id) {
    const record = this.builds.get(id);
    if (!record) throw new WorkbenchError("build_not_found", "Build was not found.", 404);
    return this.publicRecord(record);
  }

  requireCompleted(id) {
    const record = this.builds.get(id);
    if (!record) throw new WorkbenchError("build_not_found", "Build was not found.", 404);
    if (record.status !== "completed") throw new WorkbenchError("build_not_ready", "Build is not complete.", 409);
    return record;
  }

  publicRecord(record) {
    return {
      build_id: record.id,
      run_id: record.run_id,
      kind: record.kind,
      status: record.status,
      source_commit: record.source_commit,
      source_clean: record.source_clean,
      artifact: record.artifact,
      error: record.error,
      started_at: record.started_at,
      completed_at: record.completed_at,
    };
  }
}
