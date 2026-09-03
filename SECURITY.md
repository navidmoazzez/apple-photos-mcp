# Security

## What this server can reach

The Apple Photos library on the Mac it runs on, and nothing else. There is no HTTP client in this package, no account, and no telemetry. No photo, thumbnail or piece of metadata is uploaded anywhere.

Previews produced by `look_at_photos` are returned through MCP to whichever model the user is already talking to. That is the purpose of the tool, and it is the only path by which image data leaves the machine.

Reads open the library's SQLite directly and never launch Photos.app. Writes go through Photos.app via AppleScript, because editing that database underneath a running Photos is how libraries get corrupted.

## What it cannot do

- **It cannot delete photos.** macOS does not expose scripted deletion to any application. `archive_photos` moves items into an album for the user to empty by hand.
- **It cannot act on items it was not given.** There are no wildcard writes. Every write names explicit uuids or filenames, capped at 100 per call.
- **It cannot write at all** when `APPLE_PHOTOS_READ_ONLY=1` is set. The write tools are not registered, so they do not appear in the tool list.

## Deliberately not implemented

**No delete, and no approximation of one.** Not an oversight. Apple blocks it for every app, and a tool that emptied the Recently Deleted album or moved files on disk would be working around a protection the user is relying on.

**No HTTP transport and no Docker image.** Not because remote access is impossible, it is not, but because the safe way to do it is a relay: a remote server that queues work and a local agent that carries it out, so no port on the Mac is ever exposed. Shipping a listening HTTP server in this package would instead invite people to open a personal photo library to the internet directly, which is the version worth avoiding.

## Credentials

There are none. Access is granted by macOS Full Disk Access to the host application, and revoked the same way in System Settings, Privacy & Security.

## Local state

| Path | Contents |
|---|---|
| `~/.apple-photos-mcp/index/` | Compressed text metadata. Filenames, dates, labels, places, OCR text. No image data. |
| `~/.apple-photos-mcp/previews/` | Downscaled JPEG previews. |

Both are written with the user's own permissions. Delete `~/.apple-photos-mcp/` to clear them.

## Prompt injection

Text read out of a user's own photos is mostly OCR of things they photographed, so the exposure is smaller than a server that reads a public feed or an inbox. It is not zero: a screenshot of a web page can contain text written to look like instructions, and screenshots are a large share of a typical library.

The server instructions frame tool output as data to report on rather than instructions to follow. That helps and it is not complete. For an agent working unattended, `APPLE_PHOTOS_READ_ONLY=1` is the real defense.

## Reporting a vulnerability

[Report it privately](https://github.com/thenavidm/apple-photos-mcp-cli/security/advisories/new). Please do not open a public issue for a security problem: an issue is visible to everyone the moment you file it, including whoever would use the bug.

## Good-faith research

Read, run and pull apart anything here. Nobody but the maintainer can change
this repository, so nothing you do while investigating puts it at risk.

The care is owed to the service the tool talks to, not to the code. When
testing, use your own account and your own data. Do not point it at somebody
else's, and do not hammer a shared API to the point where other people notice.
If a test could affect anyone but you, stop and send a private report first.

Research done in that spirit is welcome, and nothing here is a trap.
