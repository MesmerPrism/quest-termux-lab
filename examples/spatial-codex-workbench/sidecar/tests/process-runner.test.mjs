import assert from "node:assert/strict";
import test from "node:test";
import { ProcessRunner } from "../src/process-runner.mjs";

test("process runner captures bounded output without a shell", async () => {
  const runner = new ProcessRunner();
  const lines = [];
  const result = await runner.run(process.execPath, ["-e", "console.log('one'); console.log('two')"], {
    timeoutMs: 5000,
    onStdoutLine: (line) => lines.push(line),
  });
  assert.equal(result.code, 0);
  assert.deepEqual(lines, ["one", "two"]);
});
test("process runner enforces timeout", async () => {
  const runner = new ProcessRunner();
  await assert.rejects(
    () => runner.run(process.execPath, ["-e", "setInterval(() => {}, 1000)"], { timeoutMs: 50 }),
    (error) => error.code === "timeout",
  );
});
