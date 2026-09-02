/** Shared plumbing every tool uses. One spec feeds both the MCP server and the CLI. */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z, type ZodRawShape } from "zod";

import type { PythonBridge } from "../bridge.js";
import type { Config } from "../config.js";
import { PhotosError, ToolError } from "../errors.js";
import { annotationsFor, needsConfirm, type Risk, type WriteGuard } from "../safety.js";

export type ToolContext = { bridge: PythonBridge; config: Config; guard: WriteGuard };
export type ToolResult = { content: { type: "text"; text: string }[]; isError?: boolean };

export function ok(data: unknown): ToolResult {
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

  // Drop empties so Python sees its own defaults rather than nulls.
  const payload = Object.fromEntries(
    Object.entries(args).filter(([, v]) => v !== undefined && v !== null && v !== ""),
  );

  const result = await ctx.bridge.call(spec.python ?? spec.name, payload);
  if (result.isError) throw new ToolError(result.text || `${spec.name} failed.`);

  // The Python returns JSON as text. Parse it so `--json` gives real fields and
  // an MCP client gets structure rather than a string containing JSON.
  try {
    return JSON.parse(result.text);
  } catch {
    return result.text;
  }
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
