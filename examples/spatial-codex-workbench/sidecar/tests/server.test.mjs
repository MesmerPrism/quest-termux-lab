import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { createWorkbenchServer } from "../src/server.mjs";

const TEST_DIR = path.dirname(fileURLToPath(import.meta.url));
const TEMPLATE_ROOT = path.resolve(TEST_DIR, "..", "..", "demo-project");
const TOKEN = "synthetic-test-token-0123456789-abcdef";

test("server rejects missing token and exposes a typed workspace flow", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "workbench-server-"));
  const { server } = await createWorkbenchServer({ token: TOKEN, root, templateRoot: TEMPLATE_ROOT, androidJar: path.join(root, "missing-android.jar") });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  const base = `http://127.0.0.1:${address.port}`;
  const call = (route, options = {}) => fetch(`${base}${route}`, {
    ...options,
    headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json", ...(options.headers ?? {}) },
  });
  try {
    const denied = await fetch(`${base}/v1/status`);
    assert.equal(denied.status, 401);
    const status = await call("/v1/status");
    assert.equal(status.status, 200);
    const created = await call("/v1/workspaces/demo", { method: "POST", body: JSON.stringify({ workspace_id: "server-demo" }) });
    assert.equal(created.status, 201);
    const run = await call("/v1/runs", { method: "POST", body: JSON.stringify({ purpose: "server test" }) });
    assert.equal(run.status, 201);
    const repository = await call("/v1/repository/status");
    const payload = await repository.json();
    assert.equal(payload.repository.clean, true);
    assert.match(payload.repository.branch, /^codex\//);
    const missing = await call("/v1/not-real");
    assert.equal(missing.status, 404);
  } finally {
    await new Promise((resolve) => server.close(resolve));
    await rm(root, { recursive: true, force: true });
  }
});
