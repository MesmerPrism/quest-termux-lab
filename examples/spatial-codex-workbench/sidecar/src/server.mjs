import { timingSafeEqual } from "node:crypto";
import { homedir } from "node:os";
import { fileURLToPath } from "node:url";
import http from "node:http";
import path from "node:path";
import { AdbAdapter } from "./adb-adapter.mjs";
import { BuildAdapter } from "./build-adapter.mjs";
import { CodexExecRunner } from "./codex-runner.mjs";
import { createOpenAiConnectProxy } from "./connect-proxy.mjs";
import { asWorkbenchError, requireValue, WorkbenchError } from "./errors.mjs";
import { EventJournal } from "./event-journal.mjs";
import { GitHubAdapter } from "./github-adapter.mjs";
import { ProcessRunner } from "./process-runner.mjs";
import { defaultToolRegistry } from "./tool-registry.mjs";
import { publicError, redactText, safeId } from "./util.mjs";
import { WorkspaceManager } from "./workspace-manager.mjs";

const SOURCE_DIR = path.dirname(fileURLToPath(import.meta.url));
const EXAMPLE_ROOT = path.resolve(SOURCE_DIR, "..", "..");
const MAX_BODY_BYTES = 64 * 1024;

export async function createWorkbenchRuntime(overrides = {}) {
  const env = overrides.env ?? process.env;
  const token = overrides.token ?? env.WORKBENCH_TOKEN;
  requireValue(typeof token === "string" && token.length >= 32 && token.length <= 256, "token_required", "WORKBENCH_TOKEN must contain 32-256 characters.", 500);
  const tools = overrides.tools ?? defaultToolRegistry(env);
  const runner = overrides.runner ?? new ProcessRunner();
  const journal = overrides.journal ?? new EventJournal();
  const workspace = overrides.workspace ?? new WorkspaceManager({
    root: overrides.root ?? env.WORKBENCH_ROOT ?? path.join(homedir(), "codex-workspaces"),
    templateRoot: overrides.templateRoot ?? env.WORKBENCH_TEMPLATE_ROOT ?? path.join(EXAMPLE_ROOT, "demo-project"),
    tools,
    runner,
  });
  await workspace.initialize();
  const builds = new BuildAdapter({
    tools,
    runner,
    journal,
    workspace,
    androidJar: overrides.androidJar ?? env.ANDROID_JAR ?? path.join(homedir(), "quest-lab", "android-sdk", "platforms", "android-33", "android.jar"),
    keystorePath: overrides.keystorePath ?? env.WORKBENCH_KEYSTORE ?? path.join(homedir(), ".local", "share", "spatial-codex-workbench", "debug.keystore"),
  });
  const codex = new CodexExecRunner({
    tools,
    runner,
    journal,
    workspace,
    sandboxMode: overrides.codexSandbox ?? env.WORKBENCH_CODEX_SANDBOX ?? "workspace-write",
  });
  const github = new GitHubAdapter({ tools, runner, journal, workspace });
  const adb = new AdbAdapter({ tools, runner, journal, builds });
  return { token, tools, runner, journal, workspace, builds, codex, github, adb, env };
}

export async function createWorkbenchServer(overrides = {}) {
  const runtime = await createWorkbenchRuntime(overrides);
  const server = http.createServer((request, response) => {
    route(runtime, request, response).catch((error) => sendError(response, error));
  });
  return { server, runtime };
}

async function route(runtime, request, response) {
  if (request.headers.origin && runtime.env.WORKBENCH_ALLOW_BROWSER !== "1") {
    throw new WorkbenchError("origin_rejected", "Browser-origin requests are disabled.", 403);
  }
  authenticate(runtime.token, request.headers.authorization);
  const url = new URL(request.url, "http://127.0.0.1");
  const method = request.method ?? "GET";

  if (method === "GET" && url.pathname === "/v1/status") {
    return sendJson(response, 200, {
      schema: "quest-termux-lab.spatial-codex-workbench-status.v1",
      broker: "ready",
      workspace: runtime.workspace.publicCurrent(),
      active_codex: runtime.codex.activeId,
      active_build: runtime.builds.activeId,
      latest_sequence: runtime.journal.sequence,
    });
  }
  if (method === "GET" && url.pathname === "/v1/capabilities") {
    return sendJson(response, 200, { capabilities: await probeCapabilities(runtime) });
  }
  if (method === "GET" && url.pathname === "/v1/events") {
    return sendJson(response, 200, { events: runtime.journal.after(url.searchParams.get("after") ?? 0) });
  }
  if (method === "POST" && url.pathname === "/v1/workspaces/demo") {
    const body = await readJsonBody(request);
    return sendJson(response, 201, { workspace: await runtime.workspace.createDemo(body.workspace_id ?? "hello-quest") });
  }
  if (method === "POST" && url.pathname === "/v1/workspaces/clone") {
    const body = await readJsonBody(request);
    return sendJson(response, 201, { workspace: await runtime.workspace.cloneRepository({ workspaceId: body.workspace_id, url: body.url }) });
  }
  if (method === "POST" && url.pathname === "/v1/runs") {
    const body = await readJsonBody(request);
    return sendJson(response, 201, { run: await runtime.workspace.createRun(body.purpose ?? "demo") });
  }
  if (method === "POST" && url.pathname === "/v1/codex/runs") {
    const body = await readJsonBody(request);
    return sendJson(response, 202, { codex: await runtime.codex.start(body.prompt) });
  }
  if (method === "POST" && url.pathname === "/v1/codex/auth/device") {
    return sendJson(response, 202, { auth: await runtime.codex.startDeviceLogin() });
  }
  if (method === "GET" && url.pathname === "/v1/codex/auth/device") {
    return sendJson(response, 200, { auth: runtime.codex.deviceLoginStatus() });
  }
  if (method === "POST" && url.pathname === "/v1/codex/auth/device/cancel") {
    return sendJson(response, 202, { auth: runtime.codex.cancelDeviceLogin() });
  }
  const codexMatch = /^\/v1\/codex\/runs\/([A-Za-z0-9._-]+)$/.exec(url.pathname);
  if (codexMatch && method === "GET") return sendJson(response, 200, { codex: runtime.codex.get(safeId(codexMatch[1])) });
  const cancelMatch = /^\/v1\/codex\/runs\/([A-Za-z0-9._-]+)\/cancel$/.exec(url.pathname);
  if (cancelMatch && method === "POST") return sendJson(response, 202, { codex: runtime.codex.cancel(safeId(cancelMatch[1])) });
  if (method === "GET" && url.pathname === "/v1/repository/status") {
    return sendJson(response, 200, { repository: await runtime.workspace.status() });
  }
  if (method === "GET" && url.pathname === "/v1/repository/diff") {
    return sendJson(response, 200, { repository: await runtime.workspace.diff() });
  }
  if (method === "POST" && url.pathname === "/v1/repository/version/patch") {
    ensureNoActiveCodex(runtime);
    return sendJson(response, 200, { version: await runtime.workspace.bumpPatchVersion() });
  }
  if (method === "POST" && url.pathname === "/v1/repository/commit") {
    ensureNoActiveCodex(runtime);
    const body = await readJsonBody(request);
    return sendJson(response, 200, { repository: await runtime.workspace.commit({ message: body.message, reviewToken: body.review_token, files: body.files ?? null }) });
  }
  if (method === "POST" && url.pathname === "/v1/repository/discard") {
    ensureNoActiveCodex(runtime);
    const body = await readJsonBody(request);
    return sendJson(response, 200, { repository: await runtime.workspace.discard({ reviewToken: body.review_token, confirmation: body.confirmation }) });
  }
  if (method === "POST" && url.pathname === "/v1/builds") {
    ensureNoActiveCodex(runtime);
    const body = await readJsonBody(request);
    return sendJson(response, 202, { build: await runtime.builds.start(body.kind) });
  }
  const buildMatch = /^\/v1\/builds\/([A-Za-z0-9._-]+)$/.exec(url.pathname);
  if (buildMatch && method === "GET") return sendJson(response, 200, { build: runtime.builds.get(safeId(buildMatch[1])) });
  if (method === "GET" && url.pathname === "/v1/github/status") {
    return sendJson(response, 200, { github: await runtime.github.status() });
  }
  if (method === "POST" && url.pathname === "/v1/github/push-draft-pr") {
    const body = await readJsonBody(request);
    return sendJson(response, 200, { github: await runtime.github.pushDraftPr({ title: body.title, body: body.body ?? "", baseBranch: body.base_branch }) });
  }
  if (method === "GET" && url.pathname === "/v1/adb/targets") {
    return sendJson(response, 200, { targets: await runtime.adb.targets() });
  }
  if (method === "POST" && url.pathname === "/v1/deploy/install") {
    const body = await readJsonBody(request);
    return sendJson(response, 200, { deploy: await runtime.adb.install({ target: body.target, buildId: body.build_id, allowDowngrade: body.allow_downgrade ?? false }) });
  }
  if (method === "POST" && url.pathname === "/v1/deploy/launch") {
    const body = await readJsonBody(request);
    return sendJson(response, 200, { deploy: await runtime.adb.launch({ target: body.target, buildId: body.build_id }) });
  }
  throw new WorkbenchError("not_found", "Endpoint not found.", 404);
}

function ensureNoActiveCodex(runtime) {
  if (runtime.codex.activeId !== null) throw new WorkbenchError("codex_busy", "Wait for or cancel the active Codex run first.", 409);
}

function authenticate(expected, header) {
  const match = /^Bearer ([A-Za-z0-9._~-]+)$/.exec(header ?? "");
  if (!match) throw new WorkbenchError("unauthorized", "Bearer token required.", 401);
  const left = Buffer.from(expected, "utf8");
  const right = Buffer.from(match[1], "utf8");
  if (left.length !== right.length || !timingSafeEqual(left, right)) throw new WorkbenchError("unauthorized", "Bearer token rejected.", 401);
}

async function probeCapabilities(runtime) {
  const probes = [
    ["node", runtime.tools.node, ["--version"]],
    ["git", runtime.tools.git, ["--version"]],
    ["codex", runtime.tools.codex, ["--version"]],
    ["codex_auth", runtime.tools.codex, ["login", "status"]],
    ["github", runtime.tools.gh, ["--version"]],
    ["adb", runtime.tools.adb, ["version"]],
  ];
  return Promise.all(probes.map(async ([id, command, args]) => {
    try {
      const result = await runtime.runner.run(command, args, { timeoutMs: 10000, maxOutputBytes: 65536 });
      return { id, state: "ready", version: redactText((result.stdout || result.stderr).split(/\r?\n/)[0], 128) };
    } catch {
      return { id, state: "unavailable", version: null };
    }
  }));
}

async function readJsonBody(request) {
  let bytes = 0;
  const chunks = [];
  for await (const chunk of request) {
    bytes += chunk.length;
    if (bytes > MAX_BODY_BYTES) throw new WorkbenchError("body_too_large", "Request body is too large.", 413);
    chunks.push(chunk);
  }
  if (chunks.length === 0) return {};
  try {
    const parsed = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    requireValue(parsed !== null && typeof parsed === "object" && !Array.isArray(parsed), "invalid_json", "Request body must be a JSON object.");
    return parsed;
  } catch (error) {
    if (error instanceof WorkbenchError) throw error;
    throw new WorkbenchError("invalid_json", "Request body is not valid JSON.", 400);
  }
}

function sendJson(response, status, value) {
  if (response.headersSent) return;
  const body = JSON.stringify(value);
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(body),
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
  });
  response.end(body);
}

function sendError(response, error) {
  if (response.headersSent) return;
  const safe = asWorkbenchError(error);
  sendJson(response, safe.status ?? 500, { error: publicError(safe) });
}

async function main() {
  const port = Number(process.env.WORKBENCH_PORT ?? 47821);
  const proxyPort = Number(process.env.WORKBENCH_PROXY_PORT ?? 47822);
  requireValue(Number.isInteger(port) && port >= 1024 && port <= 65535, "invalid_port", "WORKBENCH_PORT is invalid.", 500);
  requireValue(Number.isInteger(proxyPort) && proxyPort >= 1024 && proxyPort <= 65535 && proxyPort !== port, "invalid_port", "WORKBENCH_PROXY_PORT is invalid.", 500);
  const { server } = await createWorkbenchServer();
  const proxy = createOpenAiConnectProxy();
  proxy.listen(proxyPort, "127.0.0.1", () => {
    server.listen(port, "127.0.0.1", () => {
      process.stdout.write(`SPATIAL_CODEX_WORKBENCH_READY port=${port} proxy=bounded\n`);
    });
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    process.stderr.write(`SPATIAL_CODEX_WORKBENCH_FAILED ${redactText(error.message, 512)}\n`);
    process.exitCode = 1;
  });
}
