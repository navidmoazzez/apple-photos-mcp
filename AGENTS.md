# CLAUDE.md

See [AGENTS.md](./AGENTS.md). One document, so the two cannot drift.

## The TypeScript surface

`src-ts/` is the MCP server and CLI; `src/apple_photos_mcp/` is the engine.
Python stays because `osxphotos` and `photoscript` are the only libraries that
can read a Photos library and both are Python-only. TypeScript wraps them for
the things Python cost us: `npx` with no toolchain, a CLI, and a tool array the
HQ connector can import.

**Add a tool to Python and to `src-ts/tools/index.ts` together.** A parity test
compares the two lists and fails when they drift. That drift is what left the
hosted connector exposing 11 of 13 tools, missing `library_stats` and
`look_at_photos`, so a model estimated library totals from keyword samples and
recommended photos it had never seen.

**Compiled output goes to `lib/`, never `dist/`.** Python packaging writes a
`dist/.gitignore` containing `*`, which silently excludes every compiled file
from the npm tarball. The package then installs with no code in it and the
failure appears somewhere else entirely.

**No `os` field in package.json.** It reads as correct and breaks the HQ build:
that route imports the tool array on a Linux builder and never executes a tool,
so the package has to install anywhere. `requireMac()` refuses to run off macOS
instead, which is the same call `pyproject.toml` makes with its platform markers.

    npm run typecheck && npm test && npm run build
    uv run pytest -q
