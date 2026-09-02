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
 * client, so the Python needs no changes and there is one implementation of
 * every tool.
 */

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

import type { Config } from "./config.js";
import { BridgeError } from "./errors.js";

/** A content part as the MCP protocol carries it: text, image, or anything later. */
export type ContentPart = { type: string; text?: string; data?: string; mimeType?: string };

export type BridgeResult = {
  /** Every part, untouched. Images must survive: look_at_photos returns them. */
  content: ContentPart[];
  /** The text parts joined, for the common case of a JSON payload. */
  text: string;
  isError: boolean;
};

export class PythonBridge {
  private readonly config: Config;
  private client?: Client;
  private starting?: Promise<Client>;
  /** The tail of the engine's stderr, so a failure can say what actually went wrong. */
  private stderrTail = "";

  constructor(config: Config) {
    this.config = config;
  }

  private async connect(): Promise<Client> {
    if (this.client) return this.client;
    if (this.starting) return this.starting;

    this.starting = (async () => {
      const client = new Client({ name: "apple-photos-cli", version: "1.0.0" }, { capabilities: {} });

      const transport = new StdioClientTransport({
        command: this.config.pythonCommand,
        args: this.config.pythonArgs,
        env: { ...process.env, ...this.config.pythonEnv } as Record<string, string>,
        stderr: "pipe",
      });

      // Drain stderr immediately. The SDK pipes it into a PassThrough with a
      // 16KB buffer; with no reader that fills, the OS pipe fills behind it,
      // and the child blocks writing to stderr. osxphotos is chatty on a large
      // library, so this is a real hang, not a theoretical one. Keeping the
      // tail also means a failure can name the actual cause — a missing module,
      // a Full Disk Access denial — instead of a boilerplate "install uv".
      transport.stderr?.on("data", (chunk: Buffer) => {
        this.stderrTail = (this.stderrTail + chunk.toString()).slice(-4000);
      });

      // A dead client must not stay cached, or one engine crash bricks every
      // later call for the life of the process with "Connection closed".
      const forget = (): void => {
        if (this.client === client) this.client = undefined;
      };
      client.onclose = forget;
      client.onerror = forget;

      try {
        // The default is 60s, and a cold `uv` run builds pyobjc, which takes
        // longer than that on a fresh cache. Failing there reported "install
        // uv" at the one moment uv was working correctly.
        await client.connect(transport, { timeout: this.config.startupTimeoutMs });
      } catch (error) {
        throw new BridgeError(
          `Could not start the Photos engine with \`${this.config.pythonCommand} ${this.config.pythonArgs.join(" ")}\`. ` +
            `Install uv (https://docs.astral.sh/uv/) or set APPLE_PHOTOS_PYTHON to a Python that has osxphotos and photoscript.`,
          [(error as Error).message, this.stderrTail.trim()].filter(Boolean).join("\n"),
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

  /**
   * Call one Python tool and return every content part.
   *
   * `timeoutMs` matters: exporting originals pulls them out of iCloud first and
   * rendering previews is not quick either, so the protocol default of 60s
   * cancels work the engine is still doing.
   */
  async call(tool: string, args: Record<string, unknown>, timeoutMs?: number): Promise<BridgeResult> {
    const client = await this.connect();

    let result: { content?: ContentPart[]; isError?: boolean };
    try {
      result = (await client.callTool(
        { name: tool, arguments: args },
        undefined,
        { timeout: timeoutMs ?? this.config.requestTimeoutMs },
      )) as { content?: ContentPart[]; isError?: boolean };
    } catch (error) {
      throw new BridgeError(
        `The Photos engine failed while running ${tool}.`,
        [(error as Error).message, this.stderrTail.trim()].filter(Boolean).join("\n"),
      );
    }

    const content = result.content ?? [];
    const text = content
      .filter((part) => part.type === "text" && typeof part.text === "string")
      .map((part) => part.text as string)
      .join("\n");

    return { content, text, isError: result.isError === true };
  }

  /** What the Python server says it offers, for checking the two lists agree. */
  async listTools(): Promise<string[]> {
    const client = await this.connect();
    const { tools } = await client.listTools();
    return tools.map((tool) => tool.name);
  }

  async close(): Promise<void> {
    this.starting = undefined;
    const client = this.client;
    this.client = undefined;
    await client?.close().catch(() => undefined);
  }
}
