/**
 * Everything read from the environment, in one place.
 *
 * There are no credentials here and there is nothing to configure to get
 * started: the library is on this Mac and macOS decides who may read it. The
 * only real setting is how to start Python.
 */

import { fileURLToPath } from "node:url";

export type Config = {
  pythonCommand: string;
  pythonArgs: string[];
  pythonEnv: Record<string, string>;
  readOnly: boolean;
  allowDestructive: boolean;
  auditPath?: string;
  exportDir?: string;
};

function bool(name: string, fallback: boolean): boolean {
  const raw = process.env[name];
  if (raw === undefined || raw.trim() === "") return fallback;
  return !["0", "false", "no", "off"].includes(raw.trim().toLowerCase());
}

function str(name: string): string | undefined {
  const raw = process.env[name];
  return raw && raw.trim() ? raw.trim() : undefined;
}

/**
 * Where the Python engine lives, resolved from this file rather than the
 * working directory.
 *
 * `src` relative to CWD works when you run from a clone and breaks everywhere
 * else, which is every `npx` install: the engine ships inside the package and
 * the caller is in their own project. dist/ sits one level under the package
 * root, so the engine is always ../src from here.
 */
function packagedEnginePath(): string {
  return fileURLToPath(new URL("../src", import.meta.url));
}

export function loadConfig(): Config {
  // `uv run --with ...` needs no virtualenv and caches after the first run, so
  // a reader with only Node installed still gets a working server.
  const explicit = str("APPLE_PHOTOS_PYTHON");
  const pythonCommand = explicit ?? "uv";
  const pythonArgs = explicit
    ? ["-m", "apple_photos_mcp"]
    : ["run", "--with", "osxphotos", "--with", "photoscript", "--with", "mcp", "python3", "-m", "apple_photos_mcp"];

  return {
    pythonCommand,
    pythonArgs,
    pythonEnv: { PYTHONPATH: str("APPLE_PHOTOS_PYTHONPATH") ?? packagedEnginePath() },
    readOnly: bool("APPLE_PHOTOS_READ_ONLY", false),
    allowDestructive: bool("APPLE_PHOTOS_ALLOW_DESTRUCTIVE", true),
    auditPath: str("APPLE_PHOTOS_AUDIT_LOG"),
    exportDir: str("APPLE_PHOTOS_EXPORT_DIR"),
  };
}

/** Every variable the code reads, so --help, the README and the tests agree. */
export const ENV_VARS = [
  "APPLE_PHOTOS_PYTHON",
  "APPLE_PHOTOS_PYTHONPATH",
  "APPLE_PHOTOS_READ_ONLY",
  "APPLE_PHOTOS_ALLOW_DESTRUCTIVE",
  "APPLE_PHOTOS_AUDIT_LOG",
  "APPLE_PHOTOS_EXPORT_DIR",
] as const;
