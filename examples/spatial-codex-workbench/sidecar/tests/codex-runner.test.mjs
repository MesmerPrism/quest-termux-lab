import assert from "node:assert/strict";
import test from "node:test";
import { CodexExecRunner, normalizeCodexEvent } from "../src/codex-runner.mjs";

test("Codex JSONL events normalize without executing their payload", () => {
  assert.deepEqual(normalizeCodexEvent({ type: "turn.started" }), {
    kind: "codex.turn_started",
    status: "running",
    summary: "Codex turn started.",
  });
  const unknown = normalizeCodexEvent({ type: "future.event", command: "rm -rf ignored" });
  assert.equal(unknown.kind, "codex.unknown_event");
  assert.doesNotMatch(unknown.summary, /rm -rf/);
});

test("Codex run refuses an unauthenticated CLI before creating an operation", async () => {
  const codex = new CodexExecRunner({
    tools: { codex: "codex" },
    runner: { run: async () => { const error = new Error("not logged in"); error.code = "process_failed"; throw error; } },
    journal: { append: () => { throw new Error("journal should not be touched"); } },
    workspace: { requireRun: () => { throw new Error("workspace should not be touched"); } },
  });
  await assert.rejects(
    codex.start("Make one safe edit."),
    (error) => error.code === "codex_not_authenticated" && error.status === 409,
  );
  assert.equal(codex.activeId, null);
});

test("Codex run passes the explicitly configured Termux sandbox fallback", async () => {
  const calls = [];
  const codex = new CodexExecRunner({
    tools: { codex: "codex" },
    runner: {
      run: async (command, args, options = {}) => {
        calls.push({ command, args, options });
        if (args[0] === "login") return { stdout: "Logged in using ChatGPT\n", stderr: "" };
        options.onStdoutLine?.(JSON.stringify({ type: "turn.completed" }));
        return { stdout: "", stderr: "" };
      },
    },
    journal: { append: () => {} },
    workspace: {
      current: { runId: "run-test" },
      requireRun: () => "/managed/demo-worktree",
    },
    sandboxMode: "danger-full-access",
  });

  const started = await codex.start("Make one safe edit.");
  for (let attempt = 0; attempt < 20 && codex.activeId !== null; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 0));
  }

  assert.equal(codex.get(started.operation_id).status, "completed");
  assert.deepEqual(calls[1].args.slice(0, 8), [
    "-a", "never", "exec", "--json", "-s", "danger-full-access", "-C", "/managed/demo-worktree",
  ]);
  assert.equal(calls[1].options.cwd, "/managed/demo-worktree");
});

test("Codex runner rejects unknown sandbox modes", () => {
  assert.throws(
    () => new CodexExecRunner({
      tools: {},
      runner: {},
      journal: {},
      workspace: {},
      sandboxMode: "unbounded-typo",
    }),
    (error) => error.code === "invalid_codex_sandbox" && error.status === 500,
  );
});
