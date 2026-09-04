import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { ProcessRunner } from "../src/process-runner.mjs";
import { defaultToolRegistry } from "../src/tool-registry.mjs";
import { WorkspaceManager } from "../src/workspace-manager.mjs";

const TEST_DIR = path.dirname(fileURLToPath(import.meta.url));
const TEMPLATE_ROOT = path.resolve(TEST_DIR, "..", "..", "demo-project");

test("demo workspace, isolated run, diff, version bump, and commit", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "workbench-workspace-"));
  const manager = new WorkspaceManager({
    root,
    templateRoot: TEMPLATE_ROOT,
    tools: defaultToolRegistry(),
    runner: new ProcessRunner(),
  });
  try {
    await manager.initialize();
    const created = await manager.createDemo("hello-test");
    assert.equal(created.base_branch, "main");
    const run = await manager.createRun("change title");
    assert.match(run.branch, /^codex\/change-title-/);
    const activity = path.join(manager.requireRun(), "src", "io", "github", "mesmerprism", "questtermuxlab", "codexdemo", "MainActivity.java");
    const original = await readFile(activity, "utf8");
    await writeFile(activity, original.replace("Built by Codex on Quest", "Tested on Quest"), "utf8");
    const firstDiff = await manager.diff();
    assert.match(firstDiff.diff, /Tested on Quest/);
    assert.equal(firstDiff.clean, false);
    const version = await manager.bumpPatchVersion();
    assert.deepEqual(version, { version_code: 2, version_name: "0.1.1" });
    const reviewed = await manager.diff();
    const committed = await manager.commit({ message: "Change demo title", reviewToken: reviewed.review_token });
    assert.equal(committed.clean, true);
    assert.match(committed.branch, /^codex\//);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
