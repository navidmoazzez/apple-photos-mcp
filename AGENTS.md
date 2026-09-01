# Working on this repo

For someone editing the server, not someone installing it. Installation is the
README.

## Run it

```bash
uv sync
uv run python -m apple_photos_mcp doctor     # fastest proof it can read the library
uv run python -m apple_photos_mcp            # stdio server
```

## Tests

```bash
uv run pytest -q
uv run ruff check src tests
```

**Tests never touch a real Photos library and never launch Photos.app.** CI runs
on a Mac with no photos on it, and a test that needs a real library is a test
nobody runs. `tests/conftest.py` builds assets by hand and fakes the library.

This has bitten once already: `add_to_album` used to open Photos.app before
checking whether any of its refs resolved, so a test that resolved nothing still
launched Photos and hung for six minutes on a permission dialog. Resolve first,
touch Photos second.

## Decisions already made

**Python, not TypeScript.** The house standard for these servers is TypeScript
with an `npx` install. This is the documented exception: `osxphotos` is the only
library that reads the Photos library database and Apple's ML metadata out of
it, and it is Python only. There is no JavaScript equivalent on npm. Building
this in TypeScript would mean shipping a Python sidecar, which costs the `npx`
story anyway and adds a process boundary for nothing.

**Reads bypass Photos.app, writes go through it.** Reading the SQLite directly
is fast and needs nothing running. Writing to that database underneath a running
Photos is how libraries get corrupted, so every write is AppleScript through
`photoscript`.

**Previews come from Apple's derivatives, not the original.** Most assets in a
modern library have no local original. `resources/derivatives/<first hex char>/`
holds thumbnails for everything, which is why previews work offline and instantly.
Prefer a real image over a `.THM` video stub, then the largest.

**Ranking weights live in `search.py:WEIGHTS`.** If you change them, run the
search tests: `test_a_real_photo_outranks_a_screenshot_that_only_mentions_the_words`
is the one that matters and it is easy to break.

**No delete tool, ever.** macOS does not expose scripted deletion to any app.
Do not add something that approximates it.

## Index cache

`~/.apple-photos-mcp/index/` holds a gzipped JSON snapshot keyed by library path
and invalidated by the library database mtime. Bump `INDEX_VERSION` in
`library.py` whenever the `Asset` shape changes, or old caches load with the
wrong fields.
