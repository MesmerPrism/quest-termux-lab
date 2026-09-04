import { redactText, safeId } from "./util.mjs";

const ALLOWED_STATUS = new Set(["pending", "running", "pass", "partial", "fail", "blocked", "canceled"]);

export class EventJournal {
  constructor({ maximumEvents = 10000 } = {}) {
    this.maximumEvents = maximumEvents;
    this.sequence = 0;
    this.events = [];
  }

  append({ operationId, runId = null, kind, status, summary }) {
    safeId(operationId, "operation_id");
    if (runId !== null) safeId(runId, "run_id");
    if (!/^[a-z][a-z0-9_.-]{0,63}$/.test(kind)) throw new Error("invalid event kind");
    if (!ALLOWED_STATUS.has(status)) throw new Error("invalid event status");
    const event = {
      schema: "quest-termux-lab.spatial-codex-workbench-event.v1",
      sequence: ++this.sequence,
      operation_id: operationId,
      run_id: runId,
      kind,
      status,
      summary: redactText(summary, 512) || "No summary",
      occurred_at: new Date().toISOString(),
    };
    this.events.push(event);
    if (this.events.length > this.maximumEvents) this.events.splice(0, this.events.length - this.maximumEvents);
    return event;
  }

  after(sequence = 0) {
    const value = Number(sequence);
    return this.events.filter((event) => event.sequence > (Number.isFinite(value) ? value : 0));
  }
}
