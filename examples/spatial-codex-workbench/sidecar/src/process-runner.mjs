import { spawn } from "node:child_process";
import { WorkbenchError } from "./errors.mjs";

export class ProcessRunner {
  async run(command, args, options = {}) {
    const {
      cwd,
      env,
      timeoutMs = 120000,
      maxOutputBytes = 2 * 1024 * 1024,
      allowExitCodes = [0],
      onStdoutLine,
      onStderrLine,
      signal,
    } = options;
    if (!Array.isArray(args) || args.some((value) => typeof value !== "string")) {
      throw new WorkbenchError("invalid_process_args", "Process arguments must be a string array.", 500);
    }

    const started = Date.now();
    const child = spawn(command, args, {
      cwd,
      env: env ? { ...process.env, ...env } : process.env,
      shell: false,
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    let stdoutPending = "";
    let stderrPending = "";
    let bytes = 0;
    let settled = false;
    let terminationReason = null;

    const terminate = (reason) => {
      if (settled || terminationReason) return;
      terminationReason = reason;
      child.kill("SIGTERM");
      setTimeout(() => {
        if (!settled) child.kill("SIGKILL");
      }, 2000).unref();
    };
    const timer = setTimeout(() => terminate("timeout"), timeoutMs);
    timer.unref();
    const abort = () => terminate("canceled");
    signal?.addEventListener("abort", abort, { once: true });

    const consume = (chunk, stream) => {
      bytes += chunk.length;
      if (bytes > maxOutputBytes) {
        terminate("output_limit");
        return;
      }
      const text = chunk.toString("utf8");
      if (stream === "stdout") {
        stdout += text;
        stdoutPending += text;
        const lines = stdoutPending.split(/\r?\n/);
        stdoutPending = lines.pop() ?? "";
        lines.forEach((line) => onStdoutLine?.(line));
      } else {
        stderr += text;
        stderrPending += text;
        const lines = stderrPending.split(/\r?\n/);
        stderrPending = lines.pop() ?? "";
        lines.forEach((line) => onStderrLine?.(line));
      }
    };
    child.stdout.on("data", (chunk) => consume(chunk, "stdout"));
    child.stderr.on("data", (chunk) => consume(chunk, "stderr"));

    const result = await new Promise((resolve, reject) => {
      child.on("error", reject);
      child.on("close", (code, closeSignal) => resolve({ code: code ?? -1, closeSignal }));
    }).finally(() => {
      settled = true;
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
    });

    if (stdoutPending) onStdoutLine?.(stdoutPending);
    if (stderrPending) onStderrLine?.(stderrPending);
    if (terminationReason) {
      throw new WorkbenchError(terminationReason, `Process stopped: ${terminationReason}.`, terminationReason === "canceled" ? 409 : 500);
    }
    if (!allowExitCodes.includes(result.code)) {
      const error = new WorkbenchError("process_failed", `Process exited with code ${result.code}.`, 500);
      error.result = { ...result, stdout, stderr, durationMs: Date.now() - started };
      throw error;
    }
    return { ...result, stdout, stderr, durationMs: Date.now() - started };
  }
}
