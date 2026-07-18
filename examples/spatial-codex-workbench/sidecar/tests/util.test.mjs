import assert from "node:assert/strict";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { EventJournal } from "../src/event-journal.mjs";
import { assertExistingPathInside, redactText, safeId } from "../src/util.mjs";

test("IDs and public event envelopes are bounded", () => {
  assert.equal(safeId("run-safe_1"), "run-safe_1");
  assert.throws(() => safeId("../escape"));
  const journal = new EventJournal({ maximumEvents: 2 });
  journal.append({ operationId: "op-1", kind: "test.started", status: "running", summary: "started" });
  journal.append({ operationId: "op-2", kind: "test.pass", status: "pass", summary: "passed" });
  journal.append({ operationId: "op-3", kind: "test.pass", status: "pass", summary: "passed" });
  assert.equal(journal.after(0).length, 2);
  assert.equal(journal.after(2)[0].sequence, 3);
});
test("redaction removes credentials and local paths", () => {
  const result = redactText("Authorization: Bearer ghp_abcdefghijklmnopqrstuvwxyz C:\\private\\run /data/data/com.termux/files/home/work");
  assert.doesNotMatch(result, /ghp_|C:\\private|\/data\/data/);
  assert.match(result, /redacted/);
});

test("real path checks reject escape", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "workbench-util-"));
  const inside = path.join(root, "inside");
  const sibling = `${root}-sibling`;
  try {
    await mkdir(inside);
    await mkdir(sibling);
    await writeFile(path.join(inside, "ok.txt"), "ok");
    await writeFile(path.join(sibling, "no.txt"), "no");
    assert.match(await assertExistingPathInside(root, path.join(inside, "ok.txt")), /ok\.txt$/);
    await assert.rejects(() => assertExistingPathInside(root, path.join(sibling, "no.txt")), /escapes/);
  } finally {
    await rm(root, { recursive: true, force: true });
    await rm(sibling, { recursive: true, force: true });
  }
});
