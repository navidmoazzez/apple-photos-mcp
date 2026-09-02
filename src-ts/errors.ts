/** Typed failures, each carrying the fix rather than just the symptom. */

export class PhotosError extends Error {
  readonly detail: string;

  constructor(message: string, detail = "") {
    super(message);
    this.name = new.target.name;
    this.detail = detail;
  }

  toJSON(): Record<string, unknown> {
    return { error: this.message, type: this.name, ...(this.detail ? { detail: this.detail.slice(0, 500) } : {}) };
  }
}

/** The Python engine could not be started. Nothing reached the library. */
export class BridgeError extends PhotosError {}

/** The engine ran but refused the request. */
export class ToolError extends PhotosError {}

/** Writes are off, or a destructive tool was called without confirmation. */
export class WriteBlockedError extends PhotosError {}
