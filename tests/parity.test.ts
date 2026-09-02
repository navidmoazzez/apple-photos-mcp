/**
 * The seam that matters: TypeScript declares the tools, Python implements them.
 *
 * If the two lists drift, the CLI offers a command the engine cannot run, or
 * the engine grows a tool nobody can reach. Neither shows up until someone
 * tries it, which is exactly the failure that left the hosted connector with 11
 * of 13 tools for months.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { ALL_TOOLS } from "../src-ts/tools/index.js";
import { flagsFor, isCliCommand, parseArgs } from "../src-ts/cli.js";
import { needsConfirm } from "../src-ts/safety.js";

const root = join(import.meta.dirname, "..");
const python = readFileSync(join(root, "src", "apple_photos_mcp", "server.py"), "utf8");

/** Tool names the Python engine actually registers. */
function pythonTools(): string[] {
  const names: string[] = [];
  const pattern = /@mcp\.tool[^\n]*\n(?:@[^\n]*\n)*\s*(?:async\s+)?def\s+(\w+)\(/g;
  for (const match of python.matchAll(pattern)) names.push(match[1] as string);
  return names;
}

describe("TypeScript and Python agree", () => {
  it("declares exactly the tools the engine implements", () => {
    expect([...ALL_TOOLS.map((t) => t.python ?? t.name)].sort()).toEqual(pythonTools().sort());
  });

  it("has no tool the engine cannot run", () => {
    const engine = new Set(pythonTools());
    for (const tool of ALL_TOOLS) {
      expect(engine.has(tool.python ?? tool.name), `${tool.name} is not implemented in Python`).toBe(true);
    }
  });
});

describe("every tool is a command", () => {
  it("routes in both spellings", () => {
    for (const tool of ALL_TOOLS) {
      expect(isCliCommand([tool.name.replace(/_/g, "-")]), tool.name).toBe(true);
      expect(isCliCommand([tool.name]), tool.name).toBe(true);
    }
  });

  it("gives every schema key a flag, and describes it", () => {
    for (const tool of ALL_TOOLS) {
      const flags = flagsFor(tool.schema);
      expect(flags.map((f) => f.key).sort(), tool.name).toEqual(Object.keys(tool.schema).sort());
      for (const flag of flags) {
        expect(flag.help.length, `${tool.name}.${flag.key} has no description`).toBeGreaterThan(0);
      }
    }
  });
});

describe("safety", () => {
  it("asks for confirmation only where it cannot be undone", () => {
    for (const tool of ALL_TOOLS) {
      const hasConfirm = Object.keys(tool.schema).includes("confirm");
      expect(hasConfirm, `${tool.name}`).toBe(needsConfirm(tool.risk));
    }
  });

  it("marks only archiving destructive", () => {
    const destructive = ALL_TOOLS.filter((t) => t.risk === "destructive").map((t) => t.name);
    expect(destructive).toEqual(["archive_photos"]);
  });
});

describe("positional arguments", () => {
  const flags = flagsFor({ ...ALL_TOOLS.find((t) => t.name === "search_photos")!.schema });

  /**
   * `search-photos "sunset"` refused the bare word, because the positional only
   * filled a *required* flag and every search argument is optional.
   */
  it("fills the first waiting flag even when nothing is required", () => {
    expect(parseArgs(["sunset"], flags).query).toBe("sunset");
  });
});
