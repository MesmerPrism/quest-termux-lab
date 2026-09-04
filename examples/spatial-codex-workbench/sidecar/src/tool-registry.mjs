export function defaultToolRegistry(env = process.env) {
  return Object.freeze({
    node: env.WORKBENCH_NODE ?? process.execPath,
    git: env.WORKBENCH_GIT ?? "git",
    codex: env.WORKBENCH_CODEX ?? "codex",
    gh: env.WORKBENCH_GH ?? "gh",
    adb: env.WORKBENCH_ADB ?? "adb",
    shell: env.WORKBENCH_SH ?? "sh",
  });
}
