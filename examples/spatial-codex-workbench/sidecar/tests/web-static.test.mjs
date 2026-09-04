import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const TEST_DIR = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(TEST_DIR, "..", "..", "web", "index.html");

test("web UI exposes the golden path without external content", async () => {
  const html = await readFile(WEB, "utf8");
  for (const marker of ["Start broker", "Sign in to Codex", "Create demo", "Run Codex", "Review diff", "Build preview", "Build candidate", "Push &amp; draft PR", "Install candidate", "Launch candidate"]) {
    assert.match(html, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
  assert.doesNotMatch(html, /<script\s+src=|<link\s+[^>]*href=|https:\/\/cdn\./i);
  assert.match(html, /window\.WorkbenchNative/);
  assert.match(html, /textContent/);
});
