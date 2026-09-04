export class WorkbenchError extends Error {
  constructor(code, message, status = 400, details = undefined) {
    super(message);
    this.name = "WorkbenchError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}
export function requireValue(condition, code, message, status = 400) {
  if (!condition) throw new WorkbenchError(code, message, status);
}

export function asWorkbenchError(error) {
  if (error instanceof WorkbenchError) return error;
  return new WorkbenchError("internal_error", "The operation failed.", 500, {
    type: error?.name ?? "Error",
  });
}
