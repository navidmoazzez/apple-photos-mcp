---
name: apple-photos
description: >
  Search, look at, organize and export the user's own Apple Photos library on
  this Mac. Use whenever the user wants to find, see, open, favorite, tag,
  album, archive or export ANY photo or video of theirs: "find my photo of...",
  "do I have a picture of...", "show me videos from...", "which receipt was
  that", "add these to an album", "export the original". Also use for questions
  about the library itself, such as how many photos there are, which places or
  people appear, or how much lives in iCloud. Everything runs locally and
  nothing is uploaded.
---

# Apple Photos

The library is read directly from disk on this Mac. Nothing is uploaded, and
nothing here can permanently delete a photo.


## Two surfaces, same tools

The MCP server is for work inside a conversation. The CLI is for scripting,
piping and one-off questions, and costs no context until it is called.

```bash
apple-photos-cli library-stats --json
apple-photos-cli search-photos "sunset" --limit 5 --screenshots exclude
apple-photos-cli photo-info --refs IMG_2073.MOV
apple-photos-cli <command> --help
```

The command is the tool name with dashes. `--select total,videos` trims the
output, which matters on a library this size.

## The one thing that matters

Search returns candidates. It does not return answers.

A filename and a list of labels tell you almost nothing about whether a photo is
the one the user meant. So the loop is always:

1. `search_photos` to get candidates.
2. `look_at_photos` on the top three to five.
3. Answer based on what you actually saw, naming the file and the date.

Skipping step 2 is how you confidently hand someone the wrong photo. Do not skip
it when the user asked you to find something specific.

## What is actually being searched

Apple runs machine learning on every photo, on the device, and writes the result
into the library. That is the index:

| Signal | What it holds |
|---|---|
| Scene labels | About 1,500 visual words: Sunset, Receipt, Dog, Whiteboard, Crowd |
| Text in image | Every word Apple's OCR read inside the picture |
| Activities | Dining, Hiking, Beach Activity, Celebration |
| Venue types | Restaurant, Cafe, Bar, and cuisine types |
| Place | Reverse geocoded city, state, country, venue name |
| Faces | Only people the user has actually named in Photos |
| Albums, keywords, titles | Only what the user typed themselves |

Two consequences worth internalizing.

**The visual vocabulary is closed.** Apple knows "Sunset" but not "golden hour",
"Crowd" but not "keynote", "Dog" but not "goofy". If a result comes back with
`unmatched_terms`, that word does not exist in this library and rephrasing the
same idea will not help. Read `did_you_mean`, or call `list_vocabulary`.

**Most libraries have almost no typed metadata.** Titles, captions and keywords
are usually empty, so searching for what the user calls a photo will fail.
Search for what the photo looks like instead.

## Finding things

```
search_photos(query="sunset beach")
search_photos(query="receipt", kind="photo")
search_photos(query="dinner", place="Stockholm", year=2024)
search_photos(query="", person="Anna", favorites_only=True, limit=20)
search_photos(query="whiteboard", screenshots="exclude")
```

Useful habits:

- Screenshots are usually noise. About one in five items in a typical library is
  a screenshot, so pass `screenshots="exclude"` unless the user wants them.
- When a phrase returns nothing, try a plainer visual word. "Man on stage"
  becomes "crowd" or "audience". "My passport" becomes "document".
- Filters beat clever phrasing. A place plus a year narrows far more reliably
  than a longer sentence.

## Looking

```
look_at_photos(refs=["<uuid>", "<uuid>", "<uuid>"])
```

This works even when the photo lives only in iCloud, because it reads the
thumbnail Apple already stored on this Mac rather than downloading the original.
It is fast, so use it freely.

Up to eight items render per call. Ask for a bigger `size` only when fine detail
matters, such as reading text off a receipt.

## Organizing

These work by default. If they are missing from the tool list, the server is
running with `APPLE_PHOTOS_READ_ONLY=1`.

```
favorite_photos(refs=[...])
favorite_photos(refs=[...], favorite=False)
add_to_album(album="Best of Bali", refs=[...])
add_keywords(refs=[...], keywords=["client work"])
set_photo_title(ref="<uuid>", title="Opening keynote")
```

Each of those is one click to undo in Photos, so none of them ask first.

## Archiving, the one that asks

```
archive_photos(refs=[...], confirm=True)
```

`archive_photos` is the only tool that requires `confirm: true`. Call it without
confirm to see what it would do, then again with confirm once the user has
actually asked for those specific items to go.

**Nothing deletes.** macOS does not let any app delete photos by script. This
moves items into an album for the user to empty by hand. Always say so rather
than implying the photos are gone.

## Exporting

```
export_originals(refs=[...], directory="~/Desktop/exports")
```

Full quality originals, written to a folder on this Mac. For iCloud-only photos
each one downloads first, so this is much slower than looking. If the user only
wants to see a photo, look at it instead.

## Library questions

```
library_stats()          # totals, albums, named people, how much is in iCloud
list_vocabulary()        # the visual words this library knows
photo_info(refs=[...])   # everything about specific items, including OCR text
doctor()                 # run this first whenever anything misbehaves
```

## When something breaks

| Symptom | Cause | Fix |
|---|---|---|
| Permission denied on the library | No Full Disk Access | System Settings, Privacy & Security, Full Disk Access. Add the app running the server, then fully quit and reopen it. |
| Write tools are missing entirely | `APPLE_PHOTOS_READ_ONLY=1` is set | Unset it and restart the client |
| A write fails but reads work | Photos automation not allowed | Approve the one-time popup, or System Settings, Privacy & Security, Automation |
| No preview for one photo | iCloud-only with no cached thumbnail | Open it once in Photos, or export it |
| Library not found | Photos has never run, or a non-default library | Set `APPLE_PHOTOS_LIBRARY` to the .photoslibrary path |

Run `doctor()` before guessing. It names which of these it is.
