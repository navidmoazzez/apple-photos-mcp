/**
 * One test per bug found in the 1.0.3 review.
 *
 * The parity suite next door only matched tool names out of the engine, so it
 * was green while every one of these was live. A name check is not a contract.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { ALL_TOOLS } from "../src-ts/tools/index.js";
import { FLAG_ALIASES, SYNONYMS, flagsFor, isCliCommand, parseArgs, whichCommand } from "../src-ts/cli.js";
import { ok } from "../src-ts/tools/kit.js";
import { loadConfig } from "../src-ts/config.js";

const root = join(import.meta.dirname, "..");
const python = readFileSync(join(root, "src", "apple_photos_mcp", "server.py"), "utf8");
const schemaOf = (name: string) => ALL_TOOLS.find((t) => t.name === name)!.schema as Record<string, { _def: unknown }>;

/** Pull a numeric bound out of the engine, so the test tracks it rather than a copy. */
function clamp(pattern: RegExp): number {
  const m = python.match(pattern);
  if (!m) throw new Error(`engine clamp not found: ${pattern}`);
  return Number(m[1]);
}

describe("schema bounds match the engine", () => {
  it("caps limit where the engine caps it", () => {
    const engineMax = clamp(/min\(limit,\s*(\d+)\)/);
    const check = (schemaOf("search_photos").limit as never as { _def: { innerType: { _def: { checks: { kind: string; value: number }[] } } } })
      ._def.innerType._def.checks.find((c) => c.kind === "max");
    expect(check?.value, "advertising a limit the engine silently clamps").toBe(engineMax);
  });

  it("floors preview size where the engine floors it", () => {
    const engineMin = clamp(/max\((\d+),\s*min\(size/);
    const check = (schemaOf("look_at_photos").size as never as { _def: { innerType: { _def: { checks: { kind: string; value: number }[] } } } })
      ._def.innerType._def.checks.find((c) => c.kind === "min");
    expect(check?.value).toBe(engineMin);
  });
});

describe("images survive the bridge", () => {
  /**
   * look_at_photos returns text captions interleaved with images. Serialising
   * that into a string deleted every picture, leaving the one tool whose whole
   * purpose is seeing returning filenames.
   */
  it("passes content parts through untouched", () => {
    const parts = [
      { type: "text", text: "IMG_1.jpg" },
      { type: "image", data: "AAAA", mimeType: "image/jpeg" },
    ];
    expect(ok(parts).content).toEqual(parts);
  });

  it("still serialises ordinary data", () => {
    expect(ok({ total: 3 }).content[0]?.text).toContain("total");
  });
});

describe("CLI arguments", () => {
  const refFlags = flagsFor(schemaOf("photo_info"));

  it("takes several bare refs", () => {
    expect(parseArgs(["uuid1", "uuid2", "uuid3"], refFlags).refs).toEqual(["uuid1", "uuid2", "uuid3"]);
  });

  it("still refuses a second positional for a non-repeatable flag", () => {
    const flags = flagsFor(schemaOf("set_photo_title"));
    expect(() => parseArgs(["a", "b", "c"], flags)).toThrow(/Unexpected argument/);
  });
});

describe("no leftovers from the repo this CLI was adapted from", () => {
  it("advertises no command that does not exist", () => {
    for (const phantom of ["login", "capture", "imagine", "whoami"]) {
      expect(isCliCommand([phantom]), `${phantom} is advertised but unroutable`).toBe(false);
    }
  });

  it("aliases only keys some tool declares", () => {
    const keys = new Set(ALL_TOOLS.flatMap((t) => Object.keys(t.schema)));
    for (const [alias, key] of Object.entries(FLAG_ALIASES)) {
      expect(keys.has(key), `--${alias} points at '${key}', which no tool declares`).toBe(true);
    }
  });

  it("maps synonyms onto vocabulary the tools contain", () => {
    const vocabulary = new Set(
      ALL_TOOLS.flatMap((t) => `${t.name} ${t.title} ${t.description}`.toLowerCase().split(/[^a-z0-9]+/)),
    );
    for (const target of new Set(Object.values(SYNONYMS).flat())) {
      expect(vocabulary.has(target), `synonym target '${target}' appears in no tool`).toBe(true);
    }
  });

  /** The query that returned four browsing tools and never the right one. */
  it("answers 'save my photos to disk' with export-originals", () => {
    expect(whichCommand("save my photos to disk")[0]?.tool.name).toBe("export_originals");
  });
});

describe("engine invocation", () => {
  it("passes --no-project so uv does not adopt the caller's project", () => {
    delete process.env.APPLE_PHOTOS_PYTHON;
    expect(loadConfig().pythonArgs).toContain("--no-project");
  });

  it("allows enough time for a cold start and an iCloud export", () => {
    const config = loadConfig();
    expect(config.startupTimeoutMs).toBeGreaterThan(60_000);
    expect(config.requestTimeoutMs).toBeGreaterThan(60_000);
  });
});
