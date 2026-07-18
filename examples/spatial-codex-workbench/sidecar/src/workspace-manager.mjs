import { cp, mkdir, readFile, realpath, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { WorkbenchError, requireValue } from "./errors.mjs";
import { assertExistingPathInside, boundedString, isPathInside, operationId, purposeSlug, safeId, sha256Text } from "./util.mjs";

const GITHUB_HTTPS = /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\.git)?$/;
const VERSION_CODE_PATTERN = /^VERSION_CODE=([1-9][0-9]*)$/m;
const VERSION_NAME_PATTERN = /^VERSION_NAME=([0-9A-Za-z][0-9A-Za-z.+-]{0,31})$/m;

export class WorkspaceManager {
  constructor({ root, templateRoot, tools, runner }) {
    this.root = path.resolve(root);
    this.templateRoot = path.resolve(templateRoot);
    this.tools = tools;
    this.runner = runner;
    this.sourcesRoot = path.join(this.root, "sources");
    this.runsRoot = path.join(this.root, "runs");
    this.artifactsRoot = path.join(this.root, "artifacts");
    this.stateRoot = path.join(this.root, "state");
    this.current = null;
  }

  async initialize() {
    await Promise.all([
      mkdir(this.sourcesRoot, { recursive: true }),
      mkdir(this.runsRoot, { recursive: true }),
      mkdir(this.artifactsRoot, { recursive: true }),
      mkdir(this.stateRoot, { recursive: true }),
    ]);
    await assertExistingPathInside(path.dirname(this.root), this.root, "workspace root");
  }

  async runGit(args, { cwd, allowExitCodes = [0], timeoutMs = 120000 } = {}) {
    return this.runner.run(this.tools.git, args, {
      cwd,
      allowExitCodes,
      timeoutMs,
      maxOutputBytes: 2 * 1024 * 1024,
    });
  }

  async createDemo(workspaceId = "hello-quest") {
    safeId(workspaceId, "workspace_id");
    const sourcePath = path.join(this.sourcesRoot, workspaceId);
    requireValue(isPathInside(this.sourcesRoot, sourcePath), "path_escape", "Workspace path escapes the managed source root.");
    try {
      await stat(sourcePath);
      throw new WorkbenchError("workspace_exists", "Workspace already exists.", 409);
    } catch (error) {
      if (error instanceof WorkbenchError) throw error;
      if (error.code !== "ENOENT") throw error;
    }
    await cp(this.templateRoot, sourcePath, { recursive: true, errorOnExist: true, force: false });
    await this.runGit(["init", "-b", "main"], { cwd: sourcePath });
    await this.runGit(["add", "--all"], { cwd: sourcePath });
    await this.runGit([
      "-c", "user.name=Spatial Codex Workbench",
      "-c", "user.email=workbench@example.invalid",
      "commit", "-m", "Initialize Quest APK demo",
    ], { cwd: sourcePath });
    this.current = { workspaceId, sourcePath, runId: null, runPath: null, branch: null, baseBranch: "main" };
    return this.publicCurrent();
  }

  async cloneRepository({ workspaceId, url }) {
    safeId(workspaceId, "workspace_id");
    requireValue(typeof url === "string" && GITHUB_HTTPS.test(url), "invalid_clone_url", "Only explicit HTTPS github.com repository URLs are supported.");
    const sourcePath = path.join(this.sourcesRoot, workspaceId);
    requireValue(isPathInside(this.sourcesRoot, sourcePath), "path_escape", "Workspace path escapes the managed source root.");
    try {
      await stat(sourcePath);
      throw new WorkbenchError("workspace_exists", "Workspace already exists.", 409);
    } catch (error) {
      if (error instanceof WorkbenchError) throw error;
      if (error.code !== "ENOENT") throw error;
    }
    await this.runGit(["clone", "--", url, sourcePath], { cwd: this.sourcesRoot, timeoutMs: 10 * 60 * 1000 });
    const branch = (await this.runGit(["branch", "--show-current"], { cwd: sourcePath })).stdout.trim();
    requireValue(branch.length > 0, "detached_head", "Cloned repository has a detached HEAD.", 409);
    this.current = { workspaceId, sourcePath, runId: null, runPath: null, branch: null, baseBranch: branch };
    return this.publicCurrent();
  }

  async createRun(purpose) {
    this.requireSource();
    if (this.current.runId) throw new WorkbenchError("run_exists", "A run worktree already exists for this broker session.", 409);
    const baseStatus = await this.statusAt(this.current.sourcePath);
    requireValue(baseStatus.clean, "dirty_base", "The source checkout must be clean before creating a run.", 409);
    requireValue(baseStatus.branch !== null, "detached_head", "The source checkout has a detached HEAD.", 409);
    const runId = operationId("run");
    const branch = `codex/${purposeSlug(purpose)}-${runId.slice(-8)}`;
    const runPath = path.join(this.runsRoot, runId);
    requireValue(isPathInside(this.runsRoot, runPath), "path_escape", "Run path escapes the managed run root.");
    await this.runGit(["worktree", "add", "-b", branch, runPath, "HEAD"], { cwd: this.current.sourcePath });
    await assertExistingPathInside(this.runsRoot, runPath, "run worktree");
    this.current = { ...this.current, runId, runPath, branch, baseBranch: baseStatus.branch };
    return this.publicCurrent();
  }

  requireSource() {
    if (!this.current?.sourcePath) throw new WorkbenchError("workspace_required", "Create or clone a workspace first.", 409);
    return this.current.sourcePath;
  }

  requireRun() {
    if (!this.current?.runPath) throw new WorkbenchError("run_required", "Create a run worktree first.", 409);
    return this.current.runPath;
  }

  publicCurrent() {
    if (!this.current) return null;
    return {
      workspace_id: this.current.workspaceId,
      run_id: this.current.runId,
      branch: this.current.branch,
      base_branch: this.current.baseBranch,
    };
  }

  async statusAt(cwd) {
    const [branchResult, headResult, statusResult] = await Promise.all([
      this.runGit(["branch", "--show-current"], { cwd }),
      this.runGit(["rev-parse", "HEAD"], { cwd }),
      this.runGit(["status", "--porcelain=v1", "--untracked-files=all"], { cwd }),
    ]);
    const branch = branchResult.stdout.trim() || null;
    const lines = statusResult.stdout.split(/\r?\n/).filter(Boolean);
    return {
      branch,
      head: headResult.stdout.trim(),
      clean: lines.length === 0,
      changed_files: lines.map((line) => line.slice(3).split(" -> ").pop()).filter(Boolean),
      porcelain: lines,
    };
  }

  async status() {
    const cwd = this.requireRun();
    const result = await this.statusAt(cwd);
    return { ...result, workspace_id: this.current.workspaceId, run_id: this.current.runId };
  }

  async diff({ maximumBytes = 2 * 1024 * 1024 } = {}) {
    const cwd = this.requireRun();
    const [unstaged, staged, status] = await Promise.all([
      this.runGit(["diff", "--no-ext-diff", "--unified=3", "--"], { cwd }),
      this.runGit(["diff", "--cached", "--no-ext-diff", "--unified=3", "--"], { cwd }),
      this.statusAt(cwd),
    ]);
    let text = `${unstaged.stdout}${staged.stdout}`;
    for (const line of status.porcelain.filter((entry) => entry.startsWith("?? "))) {
      const relative = line.slice(3);
      if (relative.includes("\0") || path.isAbsolute(relative) || relative.split(/[\\/]/).includes("..")) {
        throw new WorkbenchError("path_escape", "Untracked path is unsafe.", 409);
      }
      const filePath = path.join(cwd, relative);
      await assertExistingPathInside(cwd, filePath, "untracked file");
      const bytes = await readFile(filePath);
      const rendered = bytes.includes(0)
        ? `[binary untracked file: ${relative}]\n`
        : `diff --git a/${relative} b/${relative}\nnew file mode 100644\n--- /dev/null\n+++ b/${relative}\n${bytes.toString("utf8").split(/\r?\n/).map((row) => `+${row}`).join("\n")}\n`;
      text += rendered;
    }
    const truncated = Buffer.byteLength(text, "utf8") > maximumBytes;
    if (truncated) text = Buffer.from(text, "utf8").subarray(0, maximumBytes).toString("utf8");
    return {
      diff: text,
      review_token: sha256Text(text),
      truncated,
      changed_files: status.changed_files,
      clean: status.clean,
    };
  }

  async bumpPatchVersion() {
    const cwd = this.requireRun();
    const versionPath = path.join(cwd, "version.properties");
    await assertExistingPathInside(cwd, versionPath, "version file");
    const current = await readFile(versionPath, "utf8");
    const codeMatch = VERSION_CODE_PATTERN.exec(current);
    const nameMatch = VERSION_NAME_PATTERN.exec(current);
    requireValue(codeMatch && nameMatch, "invalid_version_file", "version.properties is invalid.", 409);
    const parts = nameMatch[1].split(".");
    requireValue(parts.length === 3 && parts.every((value) => /^[0-9]+$/.test(value)), "invalid_version_file", "Patch bump requires a numeric major.minor.patch version.", 409);
    const versionCode = Number(codeMatch[1]) + 1;
    const versionName = `${Number(parts[0])}.${Number(parts[1])}.${Number(parts[2]) + 1}`;
    const updated = current
      .replace(VERSION_CODE_PATTERN, `VERSION_CODE=${versionCode}`)
      .replace(VERSION_NAME_PATTERN, `VERSION_NAME=${versionName}`);
    await writeFile(versionPath, updated, "utf8");
    return { version_code: versionCode, version_name: versionName };
  }

  async commit({ message, reviewToken, files = null }) {
    const cwd = this.requireRun();
    boundedString(message, "Commit message", 200);
    const reviewed = await this.diff();
    requireValue(reviewed.review_token === reviewToken, "stale_review", "Repository changed after the reviewed diff.", 409);
    requireValue(!reviewed.truncated, "truncated_review", "The diff is too large to commit through the workbench.", 409);
    requireValue(!reviewed.clean, "nothing_to_commit", "There are no changes to commit.", 409);
    const selected = files === null ? reviewed.changed_files : files;
    requireValue(Array.isArray(selected) && selected.length > 0, "invalid_files", "Select at least one reviewed file.");
    const changed = new Set(reviewed.changed_files);
    for (const relative of selected) {
      requireValue(typeof relative === "string" && changed.has(relative), "invalid_files", "A selected file was not in the reviewed change set.");
      requireValue(!path.isAbsolute(relative) && !relative.split(/[\\/]/).includes("..") && !relative.startsWith("-"), "invalid_files", "A selected file path is unsafe.");
    }
    await this.runGit(["add", "--", ...selected], { cwd });
    await this.runGit([
      "-c", "user.name=Spatial Codex Workbench",
      "-c", "user.email=workbench@example.invalid",
      "commit", "-m", message,
    ], { cwd });
    return this.status();
  }

  async discard({ reviewToken, confirmation }) {
    const cwd = this.requireRun();
    requireValue(confirmation === "DISCARD", "confirmation_required", "Discard requires the exact confirmation word.", 409);
    const reviewed = await this.diff();
    requireValue(reviewed.review_token === reviewToken, "stale_review", "Repository changed after the reviewed diff.", 409);
    await assertExistingPathInside(this.runsRoot, cwd, "run worktree");
    await this.runGit(["reset", "--hard", "HEAD"], { cwd });
    await this.runGit(["clean", "-fd"], { cwd });
    return this.status();
  }

  async currentBranch() {
    return (await this.status()).branch;
  }

  async currentCommit() {
    return (await this.status()).head;
  }
}
