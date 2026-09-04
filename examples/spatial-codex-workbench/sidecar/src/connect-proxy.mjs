import http from "node:http";
import net from "node:net";

const MAX_CONNECTIONS = 8;
const SOCKET_TIMEOUT_MS = 2 * 60 * 1000;
const TARGET = /^([A-Za-z0-9.-]+):([0-9]{1,5})$/;

export function isAllowedOpenAiProxyTarget(authority) {
  const match = TARGET.exec(authority ?? "");
  if (!match || Number(match[2]) !== 443) return false;
  const host = match[1].toLowerCase();
  if (host.includes("..") || host.startsWith(".") || host.endsWith(".")) return false;
  return host === "openai.com" || host.endsWith(".openai.com") || host === "chatgpt.com" || host.endsWith(".chatgpt.com");
}

export function createOpenAiConnectProxy({ connect = net.connect } = {}) {
  let active = 0;
  const proxy = http.createServer((_request, response) => {
    const body = "CONNECT only.\n";
    response.writeHead(405, { "Content-Type": "text/plain", "Content-Length": Buffer.byteLength(body), "Cache-Control": "no-store" });
    response.end(body);
  });
  proxy.on("connect", (request, client, head) => {
    if (!isAllowedOpenAiProxyTarget(request.url)) {
      client.end("HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n");
      return;
    }
    if (active >= MAX_CONNECTIONS) {
      client.end("HTTP/1.1 503 Busy\r\nConnection: close\r\n\r\n");
      return;
    }
    const [host, port] = request.url.split(":");
    active += 1;
    let counted = true;
    const release = () => {
      if (!counted) return;
      counted = false;
      active -= 1;
    };
    const upstream = connect(Number(port), host);
    client.setTimeout(SOCKET_TIMEOUT_MS, () => client.destroy());
    upstream.setTimeout(SOCKET_TIMEOUT_MS, () => upstream.destroy());
    upstream.once("connect", () => {
      client.write("HTTP/1.1 200 Connection Established\r\nProxy-Agent: spatial-codex-workbench\r\n\r\n");
      if (head?.length) upstream.write(head);
      client.pipe(upstream);
      upstream.pipe(client);
    });
    // A reset tunnel can report more than one socket error while both halves
    // unwind. Persistent handlers keep a second ECONNRESET from becoming an
    // uncaught process-level error that would stop every active Codex run.
    upstream.on("error", () => client.destroy());
    client.on("error", () => upstream.destroy());
    upstream.once("close", release);
    client.once("close", () => {
      upstream.destroy();
      release();
    });
  });
  return proxy;
}
