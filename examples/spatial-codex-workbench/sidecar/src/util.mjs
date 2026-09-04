import { createHash, randomBytes } from "node:crypto";
import { realpath, stat } from "node:fs/promises";
import path from "node:path";
import { WorkbenchError, requireValue } from "./errors.mjs";

const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
const SAFE_PURPOSE = /[^a-z0-9]+/g;

export function safeId(value, label = "id") {
  requireValue(typeof value === "string" && ID_PATTERN.test(value), "invalid_id", `${label} is invalid.`);
  return value;
}

export function purposeSlug(value) {
  requireValue(typeof value === "string" && value.trim().length > 0 && value.length <= 128, "invalid_purpose", "Purpose is required and must be at most 128 characters.");
  const slug = value.toLowerCase().replace(SAFE_PURPOSE, "-").replace(/^-|-$/g, "").slice(0, 32);
  return slug || "task";
}

export function operationId(prefix = "op") {
  return `${prefix}-${randomBytes(8).toString("hex")}`;
}

export function sha256Text(value) {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

export async function sha256File(filePath) {
  const { createReadStream } = await import("node:fs");
  const hash = createHash("sha256");
  await new Promise((resolve, reject) => {
    const input = createReadStream(filePath);
    input.on("data", (chunk) => hash.update(chunk));
    input.on("error", reject);
    input.on("end", resolve);
  });
  return hash.digest("hex");
}

export function isPathInside(root, candidate) {
  const relative = path.relative(path.resolve(root), path.resolve(candidate));
  return relative !== "" && !relative.startsWith("..") && !path.isAbsolute(relative);
}

export async function assertExistingPathInside(root, candidate, label = "path") {
  const [resolvedRoot, resolvedCandidate] = await Promise.all([realpath(root), realpath(candidate)]);
  if (resolvedRoot !== resolvedCandidate && !isPathInside(resolvedRoot, resolvedCandidate)) {
    throw new WorkbenchError("path_escape", `${label} escapes the managed root.`, 400);
  }
  await stat(resolvedCandidate);
  return resolvedCandidate;
}

export function boundedString(value, label, maximum, minimum = 1) {
  requireValue(typeof value === "string", "invalid_text", `${label} must be text.`);
  requireValue(value.length >= minimum && value.length <= maximum, "invalid_text", `${label} must contain ${minimum}-${maximum} characters.`);
  requireValue(!value.includes("\0"), "invalid_text", `${label} contains a null byte.`);
  return value;
}

export function redactText(value, maximum = 2048) {
  const input = String(value ?? "");
  return input
    .replace(/(authorization\s*:\s*bearer\s+)[^\s]+/gi, "$1<redacted>")
    .replace(/\b(bearer\s+)[^\s]+/gi, "$1<redacted>")
    .replace(/\b((?:OPENAI_API_KEY|CODEX_ACCESS_TOKEN|WORKBENCH_TOKEN)\s*=\s*)[^\s]+/gi, "$1<redacted>")
    .replace(/\b(?:ghp|github_pat|sk|sess|eyJ)[A-Za-z0-9_.-]{12,}\b/g, "<redacted-token>")
    .replace(/(?:[A-Za-z]:\\|\/data\/data\/|\/home\/)[^\s"']+/g, "<local-path>")
    .slice(0, maximum);
}

export function publicError(error) {
  return {
    code: error.code ?? "operation_failed",
    message: redactText(error.message ?? "The operation failed.", 512),
  };
}
