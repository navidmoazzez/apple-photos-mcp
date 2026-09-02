/**
 * Decides whether a change is allowed to reach the library.
 *
 * The hazard here is not publishing, it is losing something. Nothing in a
 * Photos library is public, but a wrong `archive_photos` moves someone's own
 * pictures out of view, and macOS gives this process no way to put them back.
 *
 * So archiving asks. Favouriting, titling, keywording and adding to an album do
 * not: each is one click to undo in Photos, and confirming everything trains
 * the reflex that makes the confirmation on a real removal worthless.
 */

import { appendFileSync } from "node:fs";

import type { Config } from "./config.js";
import { WriteBlockedError } from "./errors.js";

export type Risk = "read" | "write" | "destructive";
export type Surface = "mcp" | "cli";

export function needsConfirm(risk: Risk): boolean {
  return risk === "destructive";
}

export class WriteGuard {
  private readonly config: Config;
  private readonly surface: Surface;

  constructor(config: Config, surface: Surface = "mcp") {
    this.config = config;
    this.surface = surface;
  }

  private get confirmFlag(): string {
    return this.surface === "cli" ? "--confirm" : "confirm: true";
  }

  get readOnly(): boolean {
    return this.config.readOnly;
  }

  check(tool: string, risk: Risk, confirm: boolean | undefined, summary: string): void {
    if (risk === "read") return;

    if (this.config.readOnly) {
      this.audit(tool, risk, summary, "blocked: read-only");
      throw new WriteBlockedError(`${tool} is unavailable: this server is running with APPLE_PHOTOS_READ_ONLY=1.`);
    }

    if (needsConfirm(risk)) {
      if (!this.config.allowDestructive) {
        this.audit(tool, risk, summary, "blocked: destructive disabled");
        throw new WriteBlockedError(`${tool} is unavailable: this server is running with APPLE_PHOTOS_ALLOW_DESTRUCTIVE=0.`);
      }
      if (confirm !== true) {
        this.audit(tool, risk, summary, "blocked: no confirm");
        throw new WriteBlockedError(
          `${tool} cannot be undone from here, so it will not run without ${this.confirmFlag}. About to: ${summary}.`,
        );
      }
    }

    this.audit(tool, risk, summary, "allowed");
  }

  private audit(tool: string, risk: Risk, summary: string, outcome: string): void {
    if (!this.config.auditPath) return;
    const line = JSON.stringify({ at: new Date().toISOString(), surface: this.surface, tool, risk, summary, outcome });
    try {
      appendFileSync(this.config.auditPath, `${line}\n`, { mode: 0o600 });
    } catch {
      // A failing audit log must never take the tool call down with it.
    }
  }
}

export function annotationsFor(risk: Risk, options: { idempotent?: boolean } = {}): Record<string, boolean> {
  return {
    readOnlyHint: risk === "read",
    destructiveHint: risk === "destructive",
    idempotentHint: options.idempotent ?? risk === "read",
    // Everything stays on this Mac: no network, no upload, nothing leaves.
    openWorldHint: false,
  };
}
