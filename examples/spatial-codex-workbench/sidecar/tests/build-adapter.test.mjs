import assert from "node:assert/strict";
import test from "node:test";
import { formatBuildFailure } from "../src/build-adapter.mjs";

test("build failures retain a bounded redacted stderr tail", () => {
  const error = new Error("Process exited with code 2.");
  error.result = {
    stderr: "first line\nmissing required tool: zipalign\n/data/data/com.termux/files/home/private/build.sh\nBearer synthetic-secret",
  };
  const message = formatBuildFailure(error);
  assert.match(message, /missing required tool: zipalign/);
  assert.match(message, /<local-path>/);
  assert.doesNotMatch(message, /synthetic-secret/);
  assert.ok(message.length <= 512);
});

test("build failure formatting favors the final diagnostic", () => {
  const error = new Error("Process failed.");
  error.result = { stderr: `${"earlier warning ".repeat(80)}\nFINAL_SIGNING_DIAGNOSTIC` };
  const message = formatBuildFailure(error);
  assert.match(message, /FINAL_SIGNING_DIAGNOSTIC/);
  assert.ok(message.length <= 512);
});
