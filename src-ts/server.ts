/** Assembles the MCP server: instructions, tools, and the read-only filter. */

import { createRequire } from "node:module";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

import { PythonBridge } from "./bridge.js";
import type { Config } from "./config.js";
import { WriteGuard } from "./safety.js";
import { ALL_TOOLS } from "./tools/index.js";
import { register, type ToolContext } from "./tools/kit.js";

const require = createRequire(import.meta.url);
const pkg = require("../package.json") as { version: string };
export const VERSION = pkg.version;

const INSTRUCTIONS = `Tools for the user's own Apple Photos library, read directly on this Mac. Nothing is uploaded anywhere.

How to actually find something:

1. search_photos first. It queries Apple's own on-device index across the whole library, so the match count is library-wide; \`limit\` caps what comes back, not what is searched.
2. Then look_at_photos on the top few. Search returns candidates, not answers, and filenames tell you nothing. Look before you describe, recommend or choose.
3. Only then reply, naming the file and the date so the user can find it.

Three things that prevent confident wrong answers:

- For anything about scale or proportion, call library_stats. It gives real totals in one call. Counting by running searches and reading results double-counts overlapping terms and cannot see the items that carry no place or label, which in a typical library is thousands.
- Apple's visual vocabulary is closed, about 1,500 words. If a result carries \`unmatched_terms\`, Apple has never heard of that word and rephrasing the same idea will not help. Read \`did_you_mean\`, or call list_vocabulary.
- Screenshots are often a fifth of a library and skew every count. Use \`screenshots: "exclude"\` when the question is about photographs.

Nothing here can delete a photo; macOS does not permit it. archive_photos moves items into an album for the user to empty by hand, and it is the one tool that asks for confirmation.`;

export type BuiltServer = { server: McpServer; bridge: PythonBridge };

export function buildServer(config: Config): BuiltServer {
  const server = new McpServer(
    { name: "apple-photos-mcp", version: VERSION },
    { capabilities: { tools: {} }, instructions: INSTRUCTIONS },
  );

  const bridge = new PythonBridge(config);
  const guard = new WriteGuard(config, "mcp");
  const context: ToolContext = { bridge, config, guard };

  // READ_ONLY removes writes from the list rather than failing them when
  // called. A model cannot call a tool it cannot see.
  const tools = ALL_TOOLS.filter((tool) => !config.readOnly || tool.risk === "read");
  for (const tool of tools) register(server, () => context, tool);

  return { server, bridge };
}
