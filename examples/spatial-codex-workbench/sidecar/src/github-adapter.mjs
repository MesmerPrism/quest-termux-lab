import { WorkbenchError, requireValue } from "./errors.mjs";
import { boundedString, redactText } from "./util.mjs";

export class GitHubAdapter {
  constructor({ tools, runner, journal, workspace }) {
    this.tools = tools;
    this.runner = runner;
    this.journal = journal;
    this.workspace = workspace;
  }

  async status() {
    try {
      const version = await this.runner.run(this.tools.gh, ["--version"], { timeoutMs: 10000, maxOutputBytes: 65536 });
      const auth = await this.runner.run(this.tools.gh, ["auth", "status", "--hostname", "github.com"], { timeoutMs: 15000, maxOutputBytes: 131072 });
      return { state: "ready", version: redactText(version.stdout.split(/\r?\n/)[0], 128), authenticated: auth.code === 0 };
    } catch (error) {
      if (error.code === "ENOENT") return { state: "unavailable", version: null, authenticated: false };
      return { state: "unauthenticated", version: null, authenticated: false };
    }
  }

  async pushDraftPr({ title, body, baseBranch }) {
    const cwd = this.workspace.requireRun();
    boundedString(title, "Pull request title", 200);
    boundedString(body, "Pull request body", 4000, 0);
    const status = await this.workspace.status();
    requireValue(status.clean, "github_requires_clean_source", "Push and draft PR require a clean worktree.", 409);
    requireValue(status.branch === this.workspace.current.branch, "branch_mismatch", "Only the current run branch may be pushed.", 409);
    requireValue(typeof baseBranch === "string" && baseBranch === this.workspace.current.baseBranch, "base_branch_mismatch", "The pull-request base must match the recorded base branch.", 409);
    const operationId = `github-${this.workspace.current.runId.slice(-8)}`;
    this.journal.append({ operationId, runId: this.workspace.current.runId, kind: "github.push_started", status: "running", summary: "GitHub branch push started." });
    try {
      await this.workspace.runGit(["push", "--set-upstream", "origin", status.branch], { cwd, timeoutMs: 5 * 60 * 1000 });
      const created = await this.runner.run(this.tools.gh, [
        "pr", "create",
        "--draft",
        "--base", baseBranch,
        "--head", status.branch,
        "--title", title,
        "--body", body,
      ], { cwd, timeoutMs: 5 * 60 * 1000, maxOutputBytes: 1024 * 1024 });
      const url = created.stdout.split(/\r?\n/).find((line) => /^https:\/\/github\.com\//.test(line.trim()))?.trim() ?? null;
      this.journal.append({ operationId, runId: this.workspace.current.runId, kind: "github.draft_pr_created", status: "pass", summary: "Branch pushed and draft pull request created." });
      return { state: "created", url, branch: status.branch, base_branch: baseBranch, head: status.head };
    } catch (error) {
      this.journal.append({ operationId, runId: this.workspace.current.runId, kind: "github.failed", status: "fail", summary: "GitHub push or draft pull request failed." });
      throw new WorkbenchError("github_failed", redactText(error.message, 512), 502);
    }
  }
}
