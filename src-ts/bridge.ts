/**
 * The bridge to the Python engine.
 *
 * Apple Photos is the one case the house standard carves out for Python: the
 * only libraries that can read a Photos library are `osxphotos` and
 * `photoscript`, both Python-only, both macOS-only, both pulling in pyobjc.
 * Reimplementing them in TypeScript would mean reimplementing Apple's private
 * SQLite schema, which is not a thing to own.
 *
 * So the engine stays Python and this layer wraps it, the way
 * google-workspace-mcp wraps the `gws` binary. What TypeScript buys is the part
 * Python cost us: `npx` with no toolchain to install first, a CLI generated
 * from the same tool array as the MCP server, and a static `ALL_TOOLS` that the
 * HQ connector can import so the hosted surface cannot drift from this one.
 *
 * Calls are proxied to the Python MCP server over stdio using the official
 * client, rather than a bespoke JSON protocol. That means the Python needs no
 * changes at all, and there is exactly one implementation of every tool.
 */

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

import type { Config } from "./config.js";
import { BridgeError } from "./errors.js";

export type BridgeResult = { text: string; isError: boolean };

/**
 * One long-lived connection to the Python server.
 *
 * Spawning per call would pay `uv`'s dependency resolution and a Photos library
 * scan every time, which is seconds each. The process is started on first use
 * and reused.
 */
export class PythonBridge {
  private readonly config: Config;
  private client?: Client;
  private starting?: Promise<Client>;

  constructor(config: Config) {
    this.config = config;
  }

  private async connect(): Promise<Client> {
    if (this.client) return this.client;
    if (this.starting) return this.starting;

    this.starting = (async () => {
      const client = new Client(
        { name: "apple-photos-cli", version: "1.0.0" },
        { capabilities: {} },
      );

      // `uv run` resolves osxphotos and photoscript on first use and caches
      // them, so the reader needs neither a virtualenv nor a pip install.
      const transport = new StdioClientTransport({
        command: this.config.pythonCommand,
        args: this.config.pythonArgs,
        env: { ...process.env, ...this.config.pythonEnv } as Record<string, string>,
        stderr: "pipe",
      });

      try {
        await client.connect(transport);
      } catch (error) {
        throw new BridgeError(
          `Could not start the Photos engine with \`${this.config.pythonCommand} ${this.config.pythonArgs.join(" ")}\`. ` +
            `Install uv (https://docs.astral.sh/uv/) or set APPLE_PHOTOS_PYTHON to a Python that has osxphotos and photoscript. ` +
            `Underlying error: ${(error as Error).message}`,
        );
      }

      this.client = client;
      return client;
    })();

    try {
      return await this.starting;
    } finally {
      this.starting = undefined;
    }
  }

  /** Call one Python tool and return its text payload. */
  async call(tool: string, args: Record<string, unknown>): Promise<BridgeResult> {
    const client = await this.connect();

    const result = (await client.callTool({ name: tool, arguments: args })) as {
      content?: { type: string; text?: string }[];
      isError?: boolean;
    };

    const text = (result.content ?? [])
      .filter((part) => part.type === "text" && typeof part.text === "string")
      .map((part) => part.text as string)
      .join("\n");

    return { text, isError: result.isError === true };
  }

  /** What the Python server says it offers. Used by `doctor` to prove the two agree. */
  async listTools(): Promise<string[]> {
    const client = await this.connect();
    const { tools } = await client.listTools();
    return tools.map((tool) => tool.name);
  }

  async close(): Promise<void> {
    await this.client?.close().catch(() => undefined);
    this.client = undefined;
  }
}
