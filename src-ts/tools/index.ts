/**
 * Every tool, mirroring the Python engine exactly.
 *
 * The names and arguments match `src/apple_photos_mcp/server.py` one for one,
 * because this layer proxies rather than reimplements. A test asserts the two
 * lists agree, so a tool added to Python and forgotten here fails the suite
 * rather than quietly going missing from the CLI and from HQ.
 */

import { z } from "zod";

import { confirmArg, defineTool, type AnyToolSpec } from "./kit.js";

const REFS = z
  .array(z.string())
  .describe("Item refs: Photos uuids from search_photos, or exact filenames like IMG_8402.mov.");

export const readTools = [
  defineTool({
    name: "search_photos",
    title: "Search the library",
    description:
      "Search the entire Photos library through Apple's own on-device index: what a picture looks like, text read inside it, the place, the activity, and any named faces.\n\nThis covers every item, not a sample. `limit` caps what comes back, not what is searched, so the match count is library-wide.\n\nApple's visual vocabulary is a closed list of roughly 1,500 words. A term it has never heard of matches nothing, and no rephrasing of the same idea helps: check `unmatched_terms` in the result, or call list_vocabulary.\n\nSearch returns candidates, not answers. The filenames tell you nothing, so call look_at_photos on the top few before describing them.",
    schema: {
      query: z.string().optional().describe("What to look for, in Apple's vocabulary. Empty returns the newest items."),
      limit: z.number().int().min(1).max(200).optional().describe("How many to return. Defaults to 12."),
      kind: z.enum(["photo", "video"]).optional().describe("Restrict to photos or videos."),
      person: z.string().optional().describe("A face the user has named in Photos."),
      album: z.string().optional().describe("Restrict to one album."),
      place: z.string().optional().describe("A place name, as Photos records it."),
      year: z.number().int().optional().describe("Restrict to one year."),
      date_from: z.string().optional().describe("ISO date, inclusive."),
      date_to: z.string().optional().describe("ISO date, inclusive."),
      favorites_only: z.boolean().optional().describe("Only items the user favourited."),
      screenshots: z
        .enum(["include", "exclude", "only"])
        .optional()
        .describe("Screenshots are a fifth of a typical library and skew any count. Defaults to include."),
      include_hidden: z.boolean().optional().describe("Include hidden items."),
    },
    risk: "read",
  }),

  defineTool({
    name: "look_at_photos",
    title: "Actually look at photos",
    description:
      "Return the images themselves so they can be looked at, rather than reasoned about from filenames and labels.\n\nCall this on the top few results before describing, recommending or choosing between them. Search gives candidates; this is the only way to know what is in them.",
    schema: {
      refs: REFS,
      size: z.number().int().min(64).max(2048).optional().describe("Longest edge in pixels. Defaults to 640."),
    },
    risk: "read",
  }),

  defineTool({
    name: "photo_info",
    title: "Full metadata for specific items",
    description:
      "Everything Photos knows about specific items: date, place, camera and lens, dimensions, albums, keywords, faces, and whether the original is on this Mac or still in iCloud.",
    schema: { refs: REFS },
    risk: "read",
  }),

  defineTool({
    name: "library_stats",
    title: "Whole-library totals",
    description:
      "Real totals for the whole library in one call: items, photos against videos, favourites, screenshots, how many carry ML labels, text or a place, named people, and every album.\n\nUse this for any question about scale or proportion. Counting by running searches and eyeballing results both costs far more and gets the wrong answer, because it double-counts overlapping terms and cannot see items with no place or label at all.",
    schema: {},
    risk: "read",
  }),

  defineTool({
    name: "list_vocabulary",
    title: "What Apple can actually search for",
    description:
      "List the scene labels Apple's index understands. The vocabulary is closed, about 1,500 words, so this is how to find the term that will match rather than guessing synonyms that cannot.",
    schema: {
      starts_with: z.string().optional().describe("Filter to labels starting with this."),
      limit: z.number().int().min(1).max(2000).optional().describe("How many to return. Defaults to 200."),
    },
    risk: "read",
  }),

  defineTool({
    name: "doctor",
    title: "Check the setup",
    description:
      "Check that the Photos library is reachable, the engine starts, and this Mac has granted the permissions needed. Run it first when something fails, because a permissions problem and an empty library look identical from a tool call.",
    schema: {},
    risk: "read",
  }),
];

export const writeTools = [
  defineTool({
    name: "export_originals",
    title: "Export originals to disk",
    description:
      "Export the original files to a folder on this Mac. Most items live in iCloud rather than on the disk, so an export downloads them first and can be slow.\n\nNothing is uploaded anywhere: the files land in a local folder and stay there.",
    schema: {
      refs: REFS,
      directory: z.string().optional().describe("Where to write. Defaults to a dated folder under ~/Downloads."),
    },
    risk: "write",
    idempotent: true,
    summary: (args) => `export ${(args.refs as string[]).length} original(s)`,
  }),

  defineTool({
    name: "favorite_photos",
    title: "Favourite or unfavourite",
    description: "Mark items as favourites, or clear the mark. One click to undo in Photos, so this does not ask for confirmation.",
    schema: {
      refs: REFS,
      favorite: z.boolean().optional().describe("False to unfavourite. Defaults to true."),
    },
    risk: "write",
    idempotent: true,
    summary: (args) => `${args.favorite === false ? "unfavourite" : "favourite"} ${(args.refs as string[]).length} item(s)`,
  }),

  defineTool({
    name: "set_photo_title",
    title: "Set a title",
    description: "Set the title on one item, as shown in Photos.",
    schema: { ref: z.string().describe("One uuid or filename."), title: z.string().describe("The title to set.") },
    risk: "write",
    idempotent: true,
    summary: (args) => `title ${String(args.ref)}`,
  }),

  defineTool({
    name: "set_photo_description",
    title: "Set a description",
    description: "Set the description, the caption field Photos shows under an item.",
    schema: {
      ref: z.string().describe("One uuid or filename."),
      description: z.string().describe("The description to set."),
    },
    risk: "write",
    idempotent: true,
    summary: (args) => `describe ${String(args.ref)}`,
  }),

  defineTool({
    name: "add_keywords",
    title: "Add keywords",
    description: "Add keywords to items. Keywords are how a library stays searchable beyond what Apple's own index recognises.",
    schema: { refs: REFS, keywords: z.array(z.string()).describe("Keywords to add.") },
    risk: "write",
    idempotent: true,
    summary: (args) => `keyword ${(args.refs as string[]).length} item(s)`,
  }),

  defineTool({
    name: "add_to_album",
    title: "Add to an album",
    description: "Add items to an album, creating it if it does not exist.",
    schema: { album: z.string().describe("Album name."), refs: REFS },
    risk: "write",
    idempotent: true,
    summary: (args) => `add ${(args.refs as string[]).length} item(s) to '${String(args.album)}'`,
  }),

  defineTool({
    name: "archive_photos",
    title: "Move items into an archive album",
    description:
      "Move items into an album for the user to review and empty by hand.\n\nThis is as close to deleting as anything here gets: macOS does not permit a process to delete from a Photos library, so nothing is destroyed, but the items leave the flow the user was looking at and only they can put them back. It needs confirmation for that reason.",
    schema: { refs: REFS, ...confirmArg },
    risk: "destructive",
    summary: (args) => `archive ${(args.refs as string[]).length} item(s)`,
  }),
];

export const ALL_TOOLS: AnyToolSpec[] = [...readTools, ...writeTools] as AnyToolSpec[];
