import { WorkbenchError, requireValue } from "./errors.mjs";
import { boundedString, operationId, redactText } from "./util.mjs";

export function normalizeCodexEvent(event) {
  const type = typeof event?.type === "string" ? event.type : "unknown";
  switch (type) {
    case "thread.started": return { kind: "codex.thread_started", status: "running", summary: "Codex thread started." };
    case "turn.started": return { kind: "codex.turn_started", status: "running", summary: "Codex turn started." };
    case "turn.completed": return { kind: "codex.turn_completed", status: "pass", summary: "Codex turn completed." };
    case "turn.failed": return { kind: "codex.turn_failed", status: "fail", summary: "Codex turn failed." };
    case "error": return { kind: "codex.error", status: "fail", summary: "Codex reported an error." };
    case "item.started": return { kind: "codex.item_started", status: "running", summary: `Codex started ${safeItemType(event.item?.type)}.` };
    case "item.updated": return { kind: "codex.item_updated", status: "running", summary: `Codex updated ${safeItemType(event.item?.type)}.` };
    case "item.completed": return { kind: "codex.item_completed", status: "running", summary: `Codex completed ${safeItemType(event.item?.type)}.` };
    default: return { kind: "codex.unknown_event", status: "partial", summary: `Codex emitted an unrecognized ${redactText(type, 64)} event.` };
  }
}

function safeItemType(value) {
  return typeof value === "string" && /^[a-z0-9_.-]{1,64}$/.test(value) ? value : "item";
}

export class CodexExecRunner {
  constructor({ tools, runner, journal, workspace, sandboxMode = "workspace-write" }) {
    requireValue(
      sandboxMode === "workspace-write" || sandboxMode === "danger-full-access",
      "invalid_codex_sandbox",
      "Codex sandbox mode must be workspace-write or danger-full-access.",
      500,
    );
    this.tools = tools;
    this.runner = runner;
    this.journal = journal;
    this.workspace = workspace;
    this.sandboxMode = sandboxMode;
    this.runs = new Map();
    this.activeId = null;
    this.authRecord = null;
    this.authController = null;
  }

  async startDeviceLogin() {
    requireValue(this.activeId === null, "codex_busy", "Wait for or cancel the active Codex run first.", 409);
    requireValue(this.authRecord?.status !== "running", "codex_auth_busy", "A Codex device-login flow is already active.", 409);
    try {
      await this.runner.run(this.tools.codex, ["login", "status"], { timeoutMs: 30000, maxOutputBytes: 256 * 1024 });
      this.authRecord = {
        operation_id: operationId("auth"),
        status: "completed",
        output: "Codex CLI is already authenticated.",
        error: null,
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
      };
      return this.publicAuthRecord();
    } catch {
      // Authentication is absent; start the explicit user-controlled flow.
    }
    const record = {
      operation_id: operationId("auth"),
      status: "running",
      output: "",
      error: null,
      started_at: new Date().toISOString(),
      completed_at: null,
    };
    this.authRecord = record;
    this.authController = new AbortController();
    this.journal.append({ operationId: record.operation_id, kind: "codex.auth_started", status: "running", summary: "Codex device login started; operator authorization is required." });
    this.executeDeviceLogin(record).catch(() => {});
    return this.publicAuthRecord();
  }

  async executeDeviceLogin(record) {
    try {
      await this.runner.run(this.tools.codex, ["login", "--device-auth"], {
        timeoutMs: 15 * 60 * 1000,
        maxOutputBytes: 1024 * 1024,
        signal: this.authController.signal,
        onStdoutLine: (line) => this.appendAuthOutput(record, line),
        onStderrLine: (line) => this.appendAuthOutput(record, line),
      });
      await this.runner.run(this.tools.codex, ["login", "status"], { timeoutMs: 30000, maxOutputBytes: 256 * 1024 });
      record.status = "completed";
      this.journal.append({ operationId: record.operation_id, kind: "codex.auth_completed", status: "pass", summary: "Codex device login completed." });
    } catch (error) {
      const canceled = error.code === "canceled";
      record.status = canceled ? "canceled" : "failed";
      record.error = { code: error.code ?? "codex_auth_failed", message: canceled ? "Device login canceled." : "Device login did not complete." };
      this.journal.append({ operationId: record.operation_id, kind: canceled ? "codex.auth_canceled" : "codex.auth_failed", status: canceled ? "canceled" : "fail", summary: canceled ? "Codex device login canceled." : "Codex device login failed." });
    } finally {
      record.completed_at = new Date().toISOString();
      this.authController = null;
    }
  }

  appendAuthOutput(record, line) {
    const safe = String(line).replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, "").replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "").slice(0, 2048);
    if (!safe) return;
    record.output = `${record.output}${safe}\n`.slice(-16384);
  }

  deviceLoginStatus() {
    return this.authRecord ? this.publicAuthRecord() : {
      operation_id: null,
      status: "idle",
      output: "",
      error: null,
      started_at: null,
      completed_at: null,
    };
  }

  cancelDeviceLogin() {
    requireValue(this.authRecord?.status === "running" && this.authController, "codex_auth_not_active", "No Codex device-login flow is active.", 409);
    this.authController.abort();
    return this.publicAuthRecord();
  }

  publicAuthRecord() {
    const record = this.authRecord;
    return {
      operation_id: record.operation_id,
      status: record.status,
      output: record.output,
      error: record.error,
      started_at: record.started_at,
      completed_at: record.completed_at,
    };
  }

  async start(prompt) {
    boundedString(prompt, "Prompt", 8192);
    requireValue(this.activeId === null, "codex_busy", "A Codex run is already active.", 409);
    requireValue(this.authRecord?.status !== "running", "codex_auth_busy", "Finish or cancel Codex device login first.", 409);
    try {
      await this.runner.run(this.tools.codex, ["login", "status"], {
        timeoutMs: 30000,
        maxOutputBytes: 256 * 1024,
      });
    } catch {
      throw new WorkbenchError(
        "codex_not_authenticated",
        "Codex CLI is not authenticated. Complete the device-login flow before starting a run.",
        409,
      );
    }
    const cwd = this.workspace.requireRun();
    const id = operationId("codex");
    const controller = new AbortController();
    const record = {
      id,
      run_id: this.workspace.current.runId,
      status: "running",
      thread_id: null,
      final_message: null,
      error: null,
      started_at: new Date().toISOString(),
      completed_at: null,
      controller,
    };
    this.runs.set(id, record);
    this.activeId = id;
    this.journal.append({ operationId: id, runId: record.run_id, kind: "codex.started", status: "running", summary: "Codex run started in the managed worktree." });
    this.execute(record, cwd, prompt).catch(() => {});
    return this.publicRecord(record);
  }

  async execute(record, cwd, prompt) {
    try {
      await this.runner.run(this.tools.codex, [
        "-a", "never",
        "exec",
        "--json",
        "-s", this.sandboxMode,
        "-C", cwd,
        prompt,
      ], {
        cwd,
        timeoutMs: 30 * 60 * 1000,
        maxOutputBytes: 16 * 1024 * 1024,
        signal: record.controller.signal,
        onStdoutLine: (line) => this.consumeLine(record, line),
      });
      if (record.status === "running") record.status = "completed";
      this.journal.append({ operationId: record.id, runId: record.run_id, kind: "codex.completed", status: "pass", summary: "Codex process completed." });
    } catch (error) {
      const canceled = error.code === "canceled";
      record.status = canceled ? "canceled" : "failed";
      record.error = { code: error.code ?? "codex_failed", message: redactText(error.message, 512) };
      this.journal.append({ operationId: record.id, runId: record.run_id, kind: canceled ? "codex.canceled" : "codex.failed", status: canceled ? "canceled" : "fail", summary: canceled ? "Codex run canceled." : "Codex process failed." });
    } finally {
      record.completed_at = new Date().toISOString();
      record.controller = null;
      if (this.activeId === record.id) this.activeId = null;
    }
  }

  consumeLine(record, line) {
    if (!line.trim()) return;
    let event;
    try {
      event = JSON.parse(line);
    } catch {
      this.journal.append({ operationId: record.id, runId: record.run_id, kind: "codex.malformed_event", status: "partial", summary: "Codex emitted a malformed JSONL event." });
      return;
    }
    if (event.type === "thread.started" && typeof event.thread_id === "string") record.thread_id = redactText(event.thread_id, 128);
    if (event.type === "item.completed" && event.item?.type === "agent_message" && typeof event.item.text === "string") {
      record.final_message = redactText(event.item.text, 4096);
    }
    const normalized = normalizeCodexEvent(event);
    this.journal.append({ operationId: record.id, runId: record.run_id, ...normalized });
  }

  cancel(id) {
    const record = this.runs.get(id);
    if (!record) throw new WorkbenchError("run_not_found", "Codex run was not found.", 404);
    if (record.status !== "running" || !record.controller) throw new WorkbenchError("run_not_active", "Codex run is not active.", 409);
    record.controller.abort();
    return this.publicRecord(record);
  }

  get(id) {
    const record = this.runs.get(id);
    if (!record) throw new WorkbenchError("run_not_found", "Codex run was not found.", 404);
    return this.publicRecord(record);
  }

  publicRecord(record) {
    return {
      operation_id: record.id,
      run_id: record.run_id,
      status: record.status,
      thread_id: record.thread_id,
      final_message: record.final_message,
      error: record.error,
      started_at: record.started_at,
      completed_at: record.completed_at,
    };
  }
}
