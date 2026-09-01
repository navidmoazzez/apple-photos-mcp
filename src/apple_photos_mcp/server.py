"""The MCP server: tool definitions and their wiring.

The tool surface is deliberately small. A large surface reads well in a table
and behaves badly in practice, because the model has to guess which of five
similar tools it wants. What matters here is that `search_photos` is genuinely
good and that `look_at_photos` exists, so the model can check its own answer
before giving it.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

# The Python MCP SDK renamed FastMCP to MCPServer in 2.0. Both are supported so
# the package keeps working whichever version a user's environment resolves.
try:  # SDK >= 2.0
    from mcp.server.mcpserver import Image
    from mcp.server.mcpserver import MCPServer as _Server
except ModuleNotFoundError:  # SDK 1.x
    from mcp.server.fastmcp import FastMCP as _Server  # type: ignore[assignment]
    from mcp.server.fastmcp import Image  # type: ignore[assignment]

from . import doctor as doctor_mod
from .config import Config
from .library import PhotosLibrary
from .previews import PreviewRenderer
from .safety import DESTRUCTIVE_WRITE, READ_ONLY_TOOL, REVERSIBLE_WRITE
from .search import Filters
from .search import search as run_search
from .writes import Writer

log = logging.getLogger(__name__)

INSTRUCTIONS = """\
This is the user's own Apple Photos library, read directly on this Mac. Nothing is
uploaded anywhere.

How to actually find something:

1. `search_photos` first. It searches Apple's own on-device index, what a photo
   looks like (scene labels), text Apple read inside it, the activity, the venue,
   the place, and any faces the user has named.
2. Then `look_at_photos` on the top few results. Search returns candidates, not
   answers, and the filenames tell you nothing. Look before you answer.
3. Only then reply, naming the file and the date so the user can find it.

Two things will save you from confident wrong answers:

* Apple's visual vocabulary is closed, about 1,500 words. If a result carries
  `unmatched_terms`, Apple has never heard of that word and no rephrasing of the
  same idea will help. Read `did_you_mean`, or call `list_vocabulary`.
* Almost every asset in a modern library lives in iCloud, not on the Mac.
  Previews still work. Exporting an original downloads it first, which is slow.

Nothing here can delete a photo. macOS does not permit it. `archive_photos` moves
items into an album for the user to empty by hand, and it is the one tool that
asks for `confirm: true` before it acts.
"""


def build_server(config: Config | None = None) -> _Server:
    config = config or Config.from_env()
    lib = PhotosLibrary(config)
    previews = PreviewRenderer(config, lib)
    writer = Writer(config, lib)

    mcp = _Server("apple-photos", instructions=INSTRUCTIONS)

    def _err(exc: Exception) -> str:
        return json.dumps({"error": str(exc)}, indent=2)

    def _json(data: Any) -> str:
        return json.dumps(data, indent=2, default=str)

    # ------------------------------------------------------------------ reads

    @mcp.tool(annotations=READ_ONLY_TOOL)
    def search_photos(
        query: str = "",
        limit: int = 12,
        kind: str | None = None,
        person: str | None = None,
        album: str | None = None,
        place: str | None = None,
        year: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        favorites_only: bool = False,
        screenshots: str = "include",
        include_hidden: bool = False,
    ) -> str:
        """Search your entire Apple Photos library using Apple's own on-device index.

        Natural visual phrases work best: 'sunset beach', 'receipt', 'dinner in
        Stockholm', 'whiteboard'. Filters narrow before ranking.

        Args:
            query: What to find. Leave empty to browse by filter alone.
            limit: Maximum results (1-100).
            kind: 'photo' or 'video'.
            person: Only photos with this named face.
            album: Only photos in albums whose name contains this.
            place: Only photos taken somewhere matching this.
            year: Only photos from this calendar year.
            date_from: ISO date, inclusive lower bound (YYYY-MM-DD).
            date_to: ISO date, inclusive upper bound (YYYY-MM-DD).
            favorites_only: Only items hearted in Photos.
            screenshots: 'include', 'exclude', or 'only'.
            include_hidden: Include items in the Hidden album.
        """
        try:
            filters = Filters(
                kind=kind if kind in ("photo", "video") else None,
                favorite=True if favorites_only else None,
                person=person,
                album=album,
                place=place,
                year=year,
                date_from=date_from,
                date_to=date_to,
                screenshots={"include": None, "exclude": False, "only": True}.get(screenshots),
                include_hidden=include_hidden,
            )
            return _json(run_search(lib, query, filters, max(1, min(limit, 100))))
        except Exception as exc:
            log.exception("search failed")
            return _err(exc)

    @mcp.tool(annotations=READ_ONLY_TOOL)
    def look_at_photos(refs: list[str], size: int = 640) -> list[str | Image]:
        """Actually look at photos: renders each one and returns it as an image.

        Use this on the top few results of every search before answering a "find
        my photo of X" question. Works even for photos that live only in iCloud,
        because it reads Apple's own local thumbnails rather than the original.

        Args:
            refs: Photo uuids from search results, or exact filenames.
            size: Longest edge in pixels (128-2048).
        """
        out: list[str | Image] = []
        size = max(128, min(size, 2048))
        for ref in refs[: config.preview_max]:
            asset = lib.get(ref)
            if asset is None:
                out.append(f"{ref}: not found in this library")
                continue
            preview = previews.render(asset, px=size)
            caption = f"{asset.filename} · {(asset.date or '')[:10]} · uuid {asset.uuid}"
            if asset.place:
                caption += f" · {asset.place}"
            out.append(caption)
            if preview.ok and preview.path is not None:
                out.append(Image(path=str(preview.path)))
            else:
                out.append(f"  (no preview: {preview.error})")
        if len(refs) > config.preview_max:
            out.append(
                f"Only the first {config.preview_max} of {len(refs)} were rendered. "
                f"Call again for the rest."
            )
        return out

    @mcp.tool(annotations=READ_ONLY_TOOL)
    def photo_info(refs: list[str]) -> str:
        """Everything known about specific photos: metadata, ML labels, place,
        albums, faces, and any text Apple read inside the image.

        Args:
            refs: Photo uuids or exact filenames.
        """
        try:
            rows = []
            for ref in refs[:50]:
                asset = lib.get(ref)
                rows.append(
                    asset.details() if asset else {"ref": ref, "error": "not found"}
                )
            return _json({"count": len(rows), "photos": rows})
        except Exception as exc:
            return _err(exc)

    @mcp.tool(annotations=READ_ONLY_TOOL)
    def library_stats() -> str:
        """Size and shape of the library: totals, albums, named people, how much
        is indexed, and how much lives only in iCloud."""
        try:
            return _json(lib.stats())
        except Exception as exc:
            return _err(exc)

    @mcp.tool(annotations=READ_ONLY_TOOL)
    def list_vocabulary(starts_with: str = "", limit: int = 200) -> str:
        """The visual words this library actually knows.

        Apple's classifier has a closed vocabulary. When a search finds nothing,
        this is how to discover the word it does understand instead.

        Args:
            starts_with: Only terms beginning with this prefix.
            limit: Maximum terms to return.
        """
        try:
            counts = lib.label_counts()
            terms = lib.vocabulary()
            if starts_with:
                terms = [t for t in terms if t.startswith(starts_with.lower())]
            ranked = sorted(terms, key=lambda t: -counts.get(t.title(), 0))[:limit]
            return _json(
                {
                    "total_terms": len(lib.vocabulary()),
                    "returned": len(ranked),
                    "terms": ranked,
                }
            )
        except Exception as exc:
            return _err(exc)

    @mcp.tool(annotations=REVERSIBLE_WRITE)
    def export_originals(refs: list[str], directory: str | None = None) -> str:
        """Export full-quality originals to a folder on this Mac.

        Slow for iCloud-only assets: each one is downloaded first. Nothing is
        uploaded anywhere.

        Args:
            refs: Photo uuids or exact filenames.
            directory: Absolute destination folder. Defaults to ~/Downloads/Photos Exports.
        """
        try:
            import osxphotos

            dest = Path(directory).expanduser() if directory else config.export_dir
            dest.mkdir(parents=True, exist_ok=True)
            uuids = []
            missing = []
            for ref in refs[: config.write_batch_max]:
                asset = lib.get(ref)
                (uuids.append(asset.uuid) if asset else missing.append(ref))
            if not uuids:
                return _json({"error": "none of those refs resolved", "unresolved": missing})

            db = osxphotos.PhotosDB(str(lib._library_path()))
            written: list[str] = []
            failed: list[dict[str, str]] = []
            for photo in db.photos(uuid=uuids):
                try:
                    written.extend(photo.export(str(dest), use_photos_export=not photo.path))
                except Exception as exc:
                    failed.append({"uuid": photo.uuid, "reason": str(exc)})
            return _json(
                {
                    "directory": str(dest),
                    "exported": len(written),
                    "files": written,
                    "failed": failed,
                    "unresolved": missing,
                }
            )
        except Exception as exc:
            log.exception("export failed")
            return _err(exc)

    @mcp.tool(annotations=READ_ONLY_TOOL)
    def doctor() -> str:
        """Diagnose setup: macOS, Full Disk Access, the library, the index, and
        whether writes are enabled. Run this first when anything misbehaves."""
        try:
            return _json(doctor_mod.run(config, lib))
        except Exception as exc:
            return _err(exc)

    # ----------------------------------------------------------------- writes
    #
    # In read-only mode these are never registered, so they do not appear in the
    # tool list at all. A model cannot call a tool it cannot see, and an error
    # message is an invitation to retry differently.
    if config.read_only:
        return mcp

    @mcp.tool(annotations=REVERSIBLE_WRITE)
    def favorite_photos(refs: list[str], favorite: bool = True) -> str:
        """Heart photos in Photos, or remove the heart.

        Args:
            refs: Photo uuids or exact filenames.
            favorite: False to un-favorite.
        """
        try:
            return _json(writer.set_favorite(refs, favorite))
        except Exception as exc:
            return _err(exc)

    @mcp.tool(annotations=REVERSIBLE_WRITE)
    def set_photo_title(ref: str, title: str) -> str:
        """Set one photo's title."""
        try:
            return _json(writer.set_title(ref, title))
        except Exception as exc:
            return _err(exc)

    @mcp.tool(annotations=REVERSIBLE_WRITE)
    def set_photo_description(ref: str, description: str) -> str:
        """Set one photo's description/caption."""
        try:
            return _json(writer.set_description(ref, description))
        except Exception as exc:
            return _err(exc)

    @mcp.tool(annotations=REVERSIBLE_WRITE)
    def add_keywords(refs: list[str], keywords: list[str]) -> str:
        """Add keywords to photos, keeping the ones already there."""
        try:
            return _json(writer.add_keywords(refs, keywords))
        except Exception as exc:
            return _err(exc)

    @mcp.tool(annotations=REVERSIBLE_WRITE)
    def add_to_album(album: str, refs: list[str]) -> str:
        """Add photos to an album, creating it if needed.

        Args:
            album: Album name.
            refs: Photo uuids or exact filenames.
        """
        try:
            return _json(writer.add_to_album(album, refs))
        except Exception as exc:
            return _err(exc)

    @mcp.tool(annotations=DESTRUCTIVE_WRITE)
    def archive_photos(refs: list[str], confirm: bool = False) -> str:
        """The closest thing to deleting that macOS allows.

        Moves photos into an archive album so they leave the main library view.
        No app, including this one, can permanently delete photos by script, so
        the user empties that album by hand.

        Args:
            refs: Photo uuids or exact filenames.
            confirm: The user reads this as deleting their photos. Set true only
                when they have actually asked for these specific items to go.
        """
        try:
            return _json(writer.archive(refs, confirm=confirm))
        except Exception as exc:
            return _err(exc)

    return mcp
