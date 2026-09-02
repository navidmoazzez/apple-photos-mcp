#!/usr/bin/env node
/**
 * Entry point.
 *
 * `apple-photos-mcp`          stdio, which is what MCP clients launch
 * `apple-photos-cli <tool>`   run one tool from the shell
 * `apple-photos-cli doctor`   check the setup and say what is wrong
 *
 * The shell surface is generated from the same `ALL_TOOLS` array the server
 * registers, so every tool is a command and neither surface can drift.
 */

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { loadConfig } from "./config.js";
import { buildServer, VERSION } from "./server.js";
import { isCliCommand, runCli } from "./cli.js";

const HELP = `apple-photos-mcp ${VERSION}

  apple-photos-mcp                 Run over stdio. This is what an MCP client launches.
  apple-photos-cli tools           List every tool as a shell command.
  apple-photos-cli <tool> [flags]  Run one tool. Same names as the MCP surface.
  apple-photos-cli <tool> --help   What that tool takes.
  apple-photos-cli doctor          Check the setup and report what is wrong.
  apple-photos-mcp --version       Print the version.

  Every command prints JSON on --json, trims it with --select, and reports
  errors as JSON on stderr.

There are no credentials. The library is on this Mac and macOS decides who may
read it; the first run will ask for permission. Nothing is uploaded anywhere.

Engine:
  APPLE_PHOTOS_PYTHON              a Python with osxphotos and photoscript.
                                   Defaults to uv, which fetches them on demand.
  APPLE_PHOTOS_PYTHONPATH          where the engine package lives, default src

Behaviour:
  APPLE_PHOTOS_EXPORT_DIR          where export_originals writes by default

Safety:
  APPLE_PHOTOS_READ_ONLY=1         hide everything that is not a read
  APPLE_PHOTOS_ALLOW_DESTRUCTIVE=0 keep reads and edits, block archiving
  APPLE_PHOTOS_AUDIT_LOG           append-only log of every attempted change

https://github.com/navidmoazzez/apple-photos-mcp-cli
`;

function invokedAsCli(): boolean {
  const name = (process.argv[1] ?? "").split("/").pop() ?? "";
  return name.startsWith("apple-photos-cli");
}

/**
 * This only runs on a Mac, but the package must still install anywhere.
 *
 * An `"os": ["darwin"]` field in package.json looks right and breaks the thing
 * that matters: the HQ connector imports ALL_TOOLS for its schemas on a Linux
 * builder, never executing a tool, and npm refuses to install at all. The
 * pyproject next door already made this call for the same reason, its comment
 * notes that platform markers make `pip install` fail on Linux "instead of
 * installing and then telling the user this server needs a Mac".
 *
 * So: install anywhere, refuse to run anywhere but macOS, and say why.
 */
function requireMac(): void {
  if (process.platform === "darwin") return;
  process.stderr.write(
    `${JSON.stringify({
      error:
        "Apple Photos only exists on macOS, so this server cannot run on " +
        `${process.platform}. It installs anywhere because the tool definitions are ` +
        "read by other tooling, but reaching a library needs a Mac.",
    }, null, 2)}\n`,
  );
  process.exit(1);
}

async function main(): Promise<void> {
  const argv = process.argv.slice(2);
  const command = argv[0];

  if (argv.includes("--version") || argv.includes("-v")) {
    process.stdout.write(`${VERSION}\n`);
    return;
  }

  if (argv.includes("--help") || argv.includes("-h") || command === "help") {
    process.stdout.write(HELP);
    return;
  }

  requireMac();

  if (invokedAsCli() && argv.length === 0) {
    process.exitCode = await runCli(["tools"]);
    return;
  }

  if (isCliCommand(argv)) {
    process.exitCode = await runCli(argv);
    return;
  }

  // Neither binary takes a positional argument that is not a command, so a
  // stray word is a typo rather than a reason to sit waiting on stdin.
  if (command !== undefined && !command.startsWith("-") && command !== "help") {
    process.stderr.write(
      `${JSON.stringify({ error: `Unknown command '${command}'. Run \`apple-photos-cli\` to list them.` }, null, 2)}\n`,
    );
    process.exitCode = 1;
    return;
  }

  if (argv.includes("--help") || argv.includes("-h") || command === "help") {
    process.stdout.write(HELP);
    return;
  }
  const built = buildServer(loadConfig());
  const transport = new StdioServerTransport();
  await built.server.connect(transport);

  const shutdown = async (): Promise<void> => {
    await built.bridge.close();
    process.exit(0);
  };
  process.on("SIGTERM", () => void shutdown());
  process.on("SIGINT", () => void shutdown());
}

main().catch((error: unknown) => {
  process.stderr.write(`[apple-photos-mcp] ${(error as Error).message}\n`);
  process.exit(1);
});
