import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import test from "node:test";
import { createOpenAiConnectProxy, isAllowedOpenAiProxyTarget } from "../src/connect-proxy.mjs";

test("CONNECT proxy accepts only OpenAI and ChatGPT HTTPS authorities", () => {
  for (const target of ["auth.openai.com:443", "api.openai.com:443", "chatgpt.com:443", "ab.chatgpt.com:443"]) {
    assert.equal(isAllowedOpenAiProxyTarget(target), true, target);
  }
  for (const target of ["openai.com:80", "openai.com.evil.invalid:443", "127.0.0.1:443", "example.com:443", "../openai.com:443"]) {
    assert.equal(isAllowedOpenAiProxyTarget(target), false, target);
  }
});

test("CONNECT proxy survives repeated socket errors", () => {
  const socket = () => Object.assign(new EventEmitter(), {
    destroy() {},
    end() {},
    pipe() {},
    setTimeout() {},
    write() {},
  });
  const upstream = socket();
  const client = socket();
  const proxy = createOpenAiConnectProxy({ connect: () => upstream });

  proxy.emit("connect", { url: "chatgpt.com:443" }, client, Buffer.alloc(0));
  client.emit("error", new Error("first client reset"));
  assert.doesNotThrow(() => client.emit("error", new Error("second client reset")));
  upstream.emit("error", new Error("first upstream reset"));
  assert.doesNotThrow(() => upstream.emit("error", new Error("second upstream reset")));
  proxy.close();
});
