/** Shared plumbing every tool uses. One spec feeds both the MCP server and the CLI. */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z, type ZodRawShape } from "zod";

import type { PythonBridge } from "../bridge.js";
import type { Config } from "../config.js";
import { PhotosError, ToolError } from "../errors.js";
import { annotationsFor, needsConfirm, type Risk, type WriteGuard } from "../safety.js";

export type ToolContext = { bridge: PythonBridge; config: Config; guard: WriteGuard };
export type ToolResult = { content: { type: string; text?: string; data?: string; mimeType?: string }[]; isError?: boolean };

export function ok(data: unknown): ToolResult {
  // Content parts that are already MCP-shaped pass straight through. That is
  // what keeps look_at_photos working: it returns images interleaved with
  // captions, and serialising them into a text blob deletes the pictures,
  // leaving a tool whose whole purpose is seeing that returns filenames.
  if (Array.isArray(data) && data.every((p) => p && typeof p === "object" && "type" in p)) {
    return { content: data as ToolResult["content"] };
  }
  const text = typeof data === "string" ? data : JSON.stringify(data, null, 2);
  return { content: [{ type: "text", text }] };
}

export function fail(error: unknown): ToolResult {
  const payload =
    error instanceof PhotosError ? error.toJSON() : { error: (error as Error)?.message ?? String(error) };
  return { content: [{ type: "text", text: JSON.stringify(payload, null, 2) }], isError: true };
}

export const confirmArg = {
  confirm: z
    .boolean()
    .optional()
    .describe("Must be true for this to run. It cannot be undone from here, so it is refused without an explicit confirmation."),
};

export type ToolSpec<S extends ZodRawShape> = {
  name: string;
  title: string;
  description: string;
  schema: S;
  risk: Risk;
  idempotent?: boolean;
  /** Override the per-call deadline. Exports pull originals out of iCloud first. */
  timeoutMs?: number;
  /** The Python tool this proxies to. Defaults to `name`. */
  python?: string;
  summary?: (args: z.infer<z.ZodObject<S>>) => string;
};

export function defineTool<S extends ZodRawShape>(spec: ToolSpec<S>): ToolSpec<S> {
  return spec;
}

export type AnyToolSpec = Omit<ToolSpec<ZodRawShape>, "summary"> & { summary?: (args: never) => string };

/**
 * Every tool runs the same way: guard, then hand the arguments to Python.
 *
 * There is no per-tool handler, because there is nothing per-tool to do. The
 * Python server already implements all thirteen; this layer exists to give them
 * a second surface, an install story and a schema HQ can import.
 */
export async function runTool(
  spec: AnyToolSpec,
  args: Record<string, unknown>,
  ctx: ToolContext,
): Promise<unknown> {
  if (spec.risk !== "read") {
    const summary = spec.summary?.(args as never) ?? spec.name;
    ctx.guard.check(spec.name, spec.risk, (args as { confirm?: boolean }).confirm, summary);
  }

  // Only undefined and null are dropped. An empty string is a real value here:
  // clearing a caption is `set_photo_description --description ""`, and
  // stripping it made the engine reject the call for a missing required
  // argument the caller had plainly supplied.
  const payload = Object.fromEntries(
    Object.entries(args).filter(([, v]) => v !== undefined && v !== null),
  );

  const result = await ctx.bridge.call(spec.python ?? spec.name, payload, spec.timeoutMs);
  if (result.isError) throw new ToolError(result.text || `${spec.name} failed.`);

  // Anything that is not plain text — images from look_at_photos — is returned
  // as content parts rather than squashed into a string.
  if (result.content.some((part) => part.type !== "text")) return result.content;

  let parsed: unknown;
  try {
    parsed = JSON.parse(result.text);
  } catch {
    return result.text;
  }

  // The engine reports its own failures as an ordinary return carrying
  // {"error": ...}, which the protocol marks successful. Without this check a
  // failed export exited 0 with the error printed on stdout, so
  // `export-originals ... && rm ...` would go on to delete the source.
  if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
    const record = parsed as Record<string, unknown>;
    if (typeof record.error === "string" && record.ok !== true) throw new ToolError(record.error);
  }
  return parsed;
}

export function register(server: McpServer, contextFor: () => ToolContext, spec: AnyToolSpec): void {
  server.registerTool(
    spec.name,
    {
      title: spec.title,
      description: spec.description,
      inputSchema: spec.schema,
      annotations: { title: spec.title, ...annotationsFor(spec.risk, { idempotent: spec.idempotent }) },
    },
    (async (args: Record<string, unknown>) => {
      try {
        return ok(await runTool(spec, args, contextFor()));
      } catch (error) {
        return fail(error);
      }
    }) as never,
  );
}

export { needsConfirm };
