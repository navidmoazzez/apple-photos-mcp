<img src="https://cdn.navid.media/connectors/apple-photos-icon.png" alt="Apple Photos" width="88">

# Apple Photos MCP

[![Stars](https://img.shields.io/github/stars/navidmoazzez/apple-photos-mcp?style=flat&logo=github&label=Stars)](https://github.com/navidmoazzez/apple-photos-mcp)
[![License](https://img.shields.io/badge/License-MIT-blue)](./LICENSE)
[![YouTube](https://img.shields.io/badge/YouTube-@thenavidm-red?logo=youtube&logoColor=white)](https://youtube.com/@thenavidm?sub_confirmation=1)
[![X](https://img.shields.io/badge/X-@thenavidm-black?logo=x)](https://x.com/thenavidm)

Give any AI agent real access to your own Apple Photos library, so it can find, see, organize and export your photos instead of guessing.

Built and maintained by [Navid Moazzez](https://navid.me?utm_source=github&utm_medium=readme&utm_campaign=apple-photos-mcp).

```
You: find the receipt from that restaurant in Cambodia

Claude: Searching 36,753 items.

  Three came back with a Receipt label and a Cambodian location.
  Let me look at them.

  It is IMG_1471, 11 May 2026, taken in S'ang, Kandal. A paper
  receipt, handwritten, stamped and signed, dated 15/01/26.

  It only exists in iCloud, so I read Apple's local thumbnail
  rather than downloading the original. Want the full quality
  file on your Desktop?
```

Everything runs on your Mac. There is no backend.

## Contents

| | Section | |
|---|---|---|
| 1 | [What you can ask it](#1-what-you-can-ask-it-) | Real prompts, not features |
| 2 | [Quick install](#2-quick-install-) | The package only |
| 3 | [Setup](#3-setup-) | One permission, once |
| 4 | [Connect your client](#4-connect-your-client-) | Every client, copy and paste |
| 5 | [Check it worked](#5-check-it-worked-) | `doctor` |
| 6 | [Tools](#6-tools-) | All 13 |
| 7 | [Working safely](#7-working-safely-) | What asks, what does not |
| 8 | [What Apple Photos actually does](#8-what-apple-photos-actually-does-) | The things that surprise people |
| 9 | [Your data](#9-your-data-) | What is stored, and where |
| 10 | [Configuration](#10-configuration-) | Every setting |
| 11 | [Troubleshooting](#11-troubleshooting-) | When something breaks |
| 12 | [FAQ](#12-faq-) | Start here if you are new |

## 1. What you can ask it 💬

- Find my photo of that whiteboard from the Bogota trip.
- Which receipts do I have from Vietnam?
- Show me videos from Dubai in 2024.
- Do I have a picture of my passport?
- How many photos do I actually have, and how many are just screenshots?
- Pull up the sunset shots from Miami Beach.
- Add these five to an album called Best of Bali.
- Export the original of that one to my Desktop.
- Which places show up most in my library?

The first one is the point. Your library already knows what is in every photo, because Apple ran machine learning across all of it on your device and wrote the results into the library. Photos gives you a search box for that. This gives an agent the entire index, so it can filter, cross-reference and then actually look at the results before answering.

## 2. Quick install ⚡

macOS, and Python 3.11 or newer.

> **Not on PyPI yet.** Install it from GitHub until it is published. The command below works today.

```bash
uvx --from git+https://github.com/navidmoazzez/apple-photos-mcp apple-photos-mcp --version
```

If you do not have [uv](https://docs.astral.sh/uv/), which is the Python equivalent of `npx`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

That completes the install. No account, no API key, no credential.

## 3. Setup 🔑

There is no login. The only setup is one macOS permission, because your Photos library is protected and an app has to be allowed to read it.

**Full Disk Access, once:**

1. Open **System Settings**.
2. Go to **Privacy & Security**, then **Full Disk Access**.
3. Click **+** and add the app that will run the server:
   - **Claude Desktop**, if you use Claude Desktop.
   - **Terminal** or **iTerm**, if you use Claude Code.
   - **Cursor**, **VS Code** or **Windsurf**, if you use one of those.
4. Make sure its toggle is on.
5. **Quit that app completely and reopen it.** Cmd+Q, not just closing the window. The permission is only picked up on a fresh launch.

That is it. Skipping step 5 is the single most common reason this looks broken.

**A second permission appears later, only if you organize.** The first time a tool changes something, macOS asks whether the app may control Photos. Click **OK**. If you miss it, it is under **Privacy & Security**, then **Automation**.

### Have an agent do it

The agent cannot grant the permission for you, because macOS deliberately requires a human. It can do everything either side of it.

Paste this into Claude Code, Cursor, or any agent with terminal access:

```
Set up apple-photos-mcp for me.

1. Install it and run `doctor`, then tell me exactly what failed.
2. Walk me through granting Full Disk Access one step at a time,
   naming the app I need to add. Stop and wait for me to confirm,
   and remind me to fully quit the app with Cmd+Q afterwards.
3. Run `doctor` again and show me how many photos it can see.
4. Then add it to my MCP client config.
```

## 4. Connect your client 🔌

### Claude Code

```bash
claude mcp add apple-photos -s user \
  -- uvx --from git+https://github.com/navidmoazzez/apple-photos-mcp apple-photos-mcp
```

`-s user` makes it available in every project rather than just the current one.

Check it registered:

```bash
claude mcp list
```

### Claude Desktop

Open **Settings**, then **Developer**, then **Edit Config**. That opens the file in your editor.

| Platform | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |

```bash
open -e ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

Apple Photos only exists on macOS, so there is no Windows or Linux path here.

**If the file is empty or new**, paste all of this:

```json
{
  "mcpServers": {
    "apple-photos": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/navidmoazzez/apple-photos-mcp", "apple-photos-mcp"]
    }
  }
}
```

**If it already has other servers**, add only the `"apple-photos"` block inside the existing `"mcpServers"` object, and put a comma after the previous server's closing brace. One misplaced comma invalidates the file, and then every server disappears, not just this one.

> **Tip**
> Claude Desktop does not inherit your shell PATH. If `uvx` is not found, run `which uvx` in a terminal and use that absolute path as `"command"`.

Quit Claude Desktop completely with Cmd+Q and reopen it.

**Logs**, when you need them:

```bash
tail -f ~/Library/Logs/Claude/mcp-server-apple-photos.log
```

### Cursor

**Cursor Settings**, then **MCP**, then **Add new global MCP server**. That opens `~/.cursor/mcp.json`. Same JSON shape as Claude Desktop, same `mcpServers` key. Save, then click reload next to the server.

For one project instead of globally, use `.cursor/mcp.json` in that project.

### Windsurf

**Windsurf Settings**, then **Cascade**, then **Model Context Protocol (MCP)**, then **Add Server**. That opens `~/.codeium/windsurf/mcp_config.json`. Same shape, key `mcpServers`. Save, then **Refresh**.

### VS Code

`.vscode/mcp.json`. The key is **`servers`**, not `mcpServers`, and each entry takes a `type`:

```json
{
  "servers": {
    "apple-photos": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "git+https://github.com/navidmoazzez/apple-photos-mcp", "apple-photos-mcp"]
    }
  }
}
```

Reload the window: Cmd+Shift+P, then **Developer: Reload Window**.

### Codex CLI

`~/.codex/config.toml`:

```toml
[mcp_servers.apple-photos]
command = "uvx"
args = ["--from", "git+https://github.com/navidmoazzez/apple-photos-mcp", "apple-photos-mcp"]
```

### Gemini CLI

`~/.gemini/settings.json`, key `mcpServers`, same shape as Claude Desktop.

### Everything else

Any stdio MCP client takes the same two things: the command `uvx`, and the args above.

### claude.ai on the web, with a relay

claude.ai runs connectors from Anthropic's cloud, so it cannot start a process on your Mac. That does not make it impossible, it makes it a two-part job.

This package ships stdio only. To reach it from a browser you put a small remote MCP server in front of it, and have a local agent on the Mac poll that server for queued work and post the results back. The cloud half is reachable from claude.ai, the Mac half holds the library, and no port on your machine is ever exposed to the internet.

That relay is not included here. It is a separate deployment with its own hosting and auth, so it is out of scope for a package you install with one command. Everything needed on the Mac side is already in this server.

## 5. Check it worked 🩺

```bash
uvx --from git+https://github.com/navidmoazzez/apple-photos-mcp apple-photos-mcp doctor
```

Or just ask your agent: **"run doctor on apple photos"**.

Healthy output includes a line like:

```json
{
  "check": "index",
  "ok": true,
  "detail": "37129 assets indexed (35983 with ML labels, 10807 with readable text)"
}
```

The two things that actually fail:

| It says | Do this |
|---|---|
| `full disk access: permission denied` | [Section 3](#3-setup-), and remember Cmd+Q |
| `library found: false` | Open Photos once, or set `APPLE_PHOTOS_LIBRARY` |

## 6. Tools 🛠️

**Finding and seeing**

| Tool | What it does |
|---|---|
| `search_photos` | Search your entire library by look, text, place, person, date |
| `look_at_photos` | Render photos so the agent can actually see them |
| `photo_info` | Everything known about specific items, including text read inside them |
| `list_vocabulary` | The visual words this library knows |

**The library itself**

| Tool | What it does |
|---|---|
| `library_stats` | Totals, albums, named people, how much is iCloud only |
| `doctor` | Diagnose setup |

**Organizing**

| Tool | What it does |
|---|---|
| `favorite_photos` | Heart items, or remove the heart |
| `add_to_album` | Add to an album, creating it if needed |
| `add_keywords` | Add keywords, keeping existing ones |
| `set_photo_title` | Set one item's title |
| `set_photo_description` | Set one item's caption |
| `archive_photos` | Move to an archive album. Needs `confirm: true` |

**Getting files out**

| Tool | What it does |
|---|---|
| `export_originals` | Full quality originals to a folder on your Mac |

## 7. Working safely 🛡️

Organizing works out of the box, because that is the point of the tool. Three things guard it.

**Nothing can delete a photo.** macOS does not expose scripted deletion to any application, and this server does not try to route around that. `archive_photos` moves items into an album so they leave your main view, and you empty that album yourself.

**`archive_photos` is the only tool that asks.** It needs `confirm: true`. Everything else it can do is one click to undo in Photos, and requiring confirmation on all of them would just teach a model to pass `confirm` reflexively, including on the one that matters.

**`APPLE_PHOTOS_READ_ONLY=1` removes every write tool.** They vanish from the tool list rather than erroring when called, because a model cannot call a tool it cannot see. This is the right setting for an agent working unattended.

`APPLE_PHOTOS_AUDIT_LOG=~/.apple-photos-mcp/writes.jsonl` records one JSON line per attempted write, allowed and blocked alike.

Every tool carries MCP annotations, so a client can decide what to auto-approve: reads are marked read-only, organizing is marked non-destructive, and `archive_photos` is marked destructive. Nothing is marked open-world, because nothing here leaves your machine.

On prompt injection: text read out of your own photos, mostly OCR, is content you photographed rather than content a stranger sent you, so the exposure is far smaller than a server that reads a public feed. It is not zero. A screenshot of a web page can contain instructions. `READ_ONLY=1` is the real defense for unattended work.

## 8. What Apple Photos actually does 📸

The part that makes this worth more than the Photos search box.

**Apple already indexed everything, on your device.** Every photo carries scene labels from a classifier with a closed vocabulary of roughly 1,500 words, the text its OCR read inside the image, a guess at the activity, the venue type, and a reverse geocoded place. None of that needs Photos.app running to read.

**Your typed metadata is almost certainly empty.** In the 37,129 item library this was built against, 3 items had a title and 3 had keywords. So searching for what you call a photo will fail. Search for what the photo looks like.

**The vocabulary is closed, and that is a real limit.** Apple knows "Sunset" but not "golden hour". Ask for a word it has never heard of and the response says so in `unmatched_terms` and suggests words that do exist, rather than quietly returning something that looks like a match. `list_vocabulary` shows every term it knows.

**Text found inside an image is weak evidence.** A screenshot full of words will match almost any query if you let it, and about one in five items in a typical library is a screenshot. Matches resting only on OCR are scored down, and screenshots compete at a discount unless you actually asked for a screenshot or a document.

**Most of your photos are not on your Mac.** iCloud keeps the originals in the cloud and leaves thumbnails behind. In the test library, 36,996 of 37,129 assets had no local original. Previews still work, because they read Apple's cached thumbnails. Exporting an original downloads it first, which is why exporting is slow and looking is not.

**Faces only work if you named them.** Photos recognizes faces on its own, but they are anonymous until you attach a name in the People album. Searching for a person only finds people you have actually named.

## 9. Your data 💾

Nothing leaves your Mac. There is no backend, no account, and no telemetry.

| What | Where | Contents |
|---|---|---|
| Search index | `~/.apple-photos-mcp/index/` | Compressed filenames, dates, labels, places and OCR text. No image data. |
| Previews | `~/.apple-photos-mcp/previews/` | Downscaled JPEGs. Safe to delete any time. |
| Audit log | Only if you set `APPLE_PHOTOS_AUDIT_LOG` | One line per attempted write. |
| Exports | `~/Downloads/Photos Exports` | Only what you explicitly export. |

Delete `~/.apple-photos-mcp/` to clear all of it.

Previews are passed to whichever model you are talking to, exactly like attaching a photo to a chat yourself. That is the purpose of `look_at_photos`, and it is the only path by which image data leaves your machine.

## 10. Configuration ⚙️

Every setting is an environment variable, set in your client's `env` block.

| Variable | Default | What it does |
|---|---|---|
| `APPLE_PHOTOS_READ_ONLY` | off | Removes every write tool from the tool list |
| `APPLE_PHOTOS_AUDIT_LOG` | off | Path for one JSON line per attempted write |
| `APPLE_PHOTOS_LIBRARY` | last opened | Path to a specific `.photoslibrary` |
| `APPLE_PHOTOS_EXPORT_DIR` | `~/Downloads/Photos Exports` | Default export folder |
| `APPLE_PHOTOS_PREVIEW_DIR` | `~/.apple-photos-mcp/previews` | Where previews are cached |
| `APPLE_PHOTOS_PREVIEW_PX` | `640` | Longest edge of a preview |
| `APPLE_PHOTOS_PREVIEW_MAX` | `8` | Most items rendered per `look_at_photos` call |
| `APPLE_PHOTOS_WRITE_BATCH_MAX` | `100` | Most items a single write may touch |
| `APPLE_PHOTOS_ARCHIVE_ALBUM` | `Archived by Claude` | Album `archive_photos` moves items into |

## 11. Troubleshooting 🔧

Run `doctor` before guessing. It names which of these it is.

| Symptom | Cause | Fix |
|---|---|---|
| Permission denied reading the library | No Full Disk Access | [Section 3](#3-setup-). Quit the app with Cmd+Q, not just the window. |
| Server does not appear in the client | Bad JSON, usually a comma | Paste the config into a JSON validator. One bad comma hides every server. |
| `uvx: command not found` | The app cannot see your shell PATH | Use the absolute path from `which uvx` |
| Write tools are missing | `APPLE_PHOTOS_READ_ONLY` is set | Unset it and restart the client |
| Reads work, writes fail | Photos automation not approved | Approve the popup, or Privacy & Security, then Automation |
| First search takes half a minute | Building the index | One time, about 25 seconds for 37,000 items. Cached afterwards. |
| A photo has no preview | iCloud only, with no cached thumbnail | Open it once in Photos, or export it |
| Search finds nothing for an obvious word | Apple has no such label | Check `unmatched_terms` in the response, or run `list_vocabulary` |

## 12. FAQ ❓

<details>
<summary><b>What is an MCP server?</b></summary>

A standard way to give an AI assistant real access to a tool, so it can act rather than guess. You install it once, your assistant gains a set of tools, and it works the same in Claude, Cursor, Codex and anything else that speaks MCP.

</details>

<details>
<summary><b>What is Apple Photos?</b></summary>

The photo app built into every Mac, iPhone and iPad. It stores your photos and videos and, on the device itself, runs machine learning over them to work out what is in each one. That analysis is what this server searches.

</details>

<details>
<summary><b>Do I need to be technical to use this?</b></summary>

You need to run one install command in Terminal and grant one macOS permission. After that you talk to it in plain English. [Section 3](#3-setup-) has an agent-guided path that walks you through the permission step by step.

</details>

<details>
<summary><b>Is my data sent anywhere? Who can see it?</b></summary>

No, and nobody. The library is read on your Mac and there is no backend, no account and no telemetry.

The one exception worth knowing: when you ask your assistant to look at a photo, that preview is sent to whichever model you are already chatting with, exactly as if you had attached it yourself. That is what makes "find my photo of X" work.

</details>

<details>
<summary><b>What can it do that I cannot do in the Photos app already?</b></summary>

Photos gives you one search box. This gives an agent the entire index at once, so it can combine things the app cannot: a scene label, a place, a date range and a person in a single query, then look at the results and tell you which one you meant.

It can also act on what it finds. "Find every receipt from Vietnam last year and put them in an album" is one sentence here and a long afternoon in the app.

</details>

<details>
<summary><b>Can it delete my photos by accident?</b></summary>

It cannot delete them at all. macOS does not allow any app to delete photos by script, so there is no delete tool and no way to add one.

The closest thing is `archive_photos`, which moves items into an album called "Archived by Claude" so they leave your main view. It refuses to run without `confirm: true`, and you empty that album yourself in Photos. Everything else it can change, favorites, albums, keywords, titles, is one click to undo.

</details>

<details>
<summary><b>Can I stop it changing anything at all?</b></summary>

Yes. Set `APPLE_PHOTOS_READ_ONLY=1` in your client config and every write tool disappears from the tool list. This is the right setting if an agent is running unattended.

</details>

<details>
<summary><b>Does it cost anything?</b></summary>

No. It is MIT licensed and it talks to nothing but your own Mac, so there is no API bill and no subscription. Your assistant's own usage is whatever you already pay for it.

</details>

<details>
<summary><b>Does it work with ChatGPT or claude.ai, or only Claude Desktop?</b></summary>

It works with any client that runs a local MCP server: Claude Code, Claude Desktop, Cursor, VS Code, Windsurf, Codex CLI, Gemini CLI.

For claude.ai in a browser you need one extra piece. Those connectors run in Anthropic's cloud and cannot start anything on your Mac, so it takes a small remote server that queues the work plus a local agent that carries it out and posts results back. It works, it is just a separate deployment rather than something this package installs for you.

</details>

<details>
<summary><b>My photos are all in iCloud and not on my Mac. Does it still work?</b></summary>

Yes for searching and looking. Apple keeps thumbnails on the Mac even when the full size original is in the cloud, and previews read those, so they are fast.

Exporting a full quality original downloads it first, which is much slower. In the library this was built against, 36,996 of 37,129 assets were iCloud only and every preview still rendered.

</details>

<details>
<summary><b>Will it slow my Mac down?</b></summary>

The first search builds an index, which takes about 25 seconds for a 37,000 item library. After that it is served from a small cache and searches take about a second. Reading does not involve Photos.app at all, so nothing has to be open.

</details>

<details>
<summary><b>How do I remove it?</b></summary>

Delete the server from your client's config, or run `claude mcp remove apple-photos` in Claude Code. Then delete `~/.apple-photos-mcp/` to remove the index and cached previews. Nothing is left behind, and nothing in your Photos library is changed by removing it.

</details>

## Questions

Run into a problem or have a question? [Open an issue](https://github.com/navidmoazzez/apple-photos-mcp/issues) and I will help.

## About the author

Navid Moazzez is a leading AI business strategist and the host of the AI Creator Summit, watched by 100,000+ creators. He helps creators and founders master AI and build their own AI Operating System (AI OS) to automate their business and life. This Apple Photos MCP server is one piece of that system.

**Links**

- Personal website: [navid.me](https://navid.me?utm_source=github&utm_medium=readme&utm_campaign=apple-photos-mcp)
- Store: [navid.bio](https://navid.bio?utm_source=github&utm_medium=readme&utm_campaign=apple-photos-mcp)
- Navid Media: [navid.media](https://navid.media?utm_source=github&utm_medium=readme&utm_campaign=apple-photos-mcp)
- YouTube: [@thenavidm](https://youtube.com/@thenavidm?sub_confirmation=1) and [@thenavidai](https://youtube.com/@thenavidai?sub_confirmation=1)
- X: [@thenavidm](https://x.com/thenavidm)
- Instagram: [@thenavidm](https://instagram.com/thenavidm)
- LinkedIn: [thenavidm](https://linkedin.com/in/thenavidm)

## Dependencies

| Package | License | Why |
|---|---|---|
| [mcp](https://github.com/modelcontextprotocol/python-sdk) | MIT | The MCP protocol implementation |
| [osxphotos](https://github.com/RhetTbull/osxphotos) | MIT | Reads the Photos library database and Apple's on-device ML metadata |
| [photoscript](https://github.com/RhetTbull/photoscript) | MIT | Drives Photos.app for writes |

## License

[MIT](./LICENSE). Free to use, modify, and share.

Not affiliated with, endorsed by, or connected to Apple Inc. Apple, macOS, Photos and iCloud are trademarks of Apple Inc.

---

© 2026 [NM Media](https://navid.media?utm_source=github&utm_medium=readme&utm_campaign=apple-photos-mcp). Made with ❤️ by [Navid Moazzez](https://navid.me?utm_source=github&utm_medium=readme&utm_campaign=apple-photos-mcp).
