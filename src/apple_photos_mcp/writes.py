"""Changing the library.

Reading uses SQLite directly. Writing cannot: Photos owns the database while it
is running, and editing it underneath the app corrupts state. Every write here
therefore goes through Photos.app itself via ``photoscript`` (AppleScript), which
is the only supported way to change a library.

Three rules hold everywhere in this module:

* **Nothing is ever deleted.** Apple does not expose scripted permanent deletion
  to any app, and this server does not try to work around that. "Delete" moves
  items into an archive album for a human to empty.
* **Batches are bounded and explicit.** No wildcards, no "everything matching".
  A caller names the items it means, up to a configured maximum.
* **Writes work by default.** Organizing a library is the point of the tool.
  `APPLE_PHOTOS_READ_ONLY=1` removes the write tools from the list entirely.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .config import Config
from .library import Asset, PhotosLibrary
from .safety import AuditLog


class WritesDisabled(RuntimeError):
    """Raised if a write is somehow reached while read-only mode is on.

    In practice the tools are never registered in that mode, so this is a
    backstop rather than the user-facing behavior.
    """

    def __init__(self) -> None:
        super().__init__(
            "This server is running in read-only mode because APPLE_PHOTOS_READ_ONLY "
            "is set. Remove it and restart the client to allow changes."
        )


class TooManyItems(ValueError):
    pass


@dataclass
class WriteResult:
    changed: list[str]
    skipped: list[dict[str, str]]

    def as_dict(self, action: str, **extra: Any) -> dict[str, Any]:
        out: dict[str, Any] = {
            "action": action,
            "changed": len(self.changed),
            "uuids": self.changed,
        }
        if self.skipped:
            out["skipped"] = self.skipped
        out.update(extra)
        return out


class Writer:
    def __init__(self, config: Config, lib: PhotosLibrary):
        self.config = config
        self.lib = lib
        self.audit = AuditLog(config)

    # ------------------------------------------------------------- guardrails

    def _guard(self, refs: list[str]) -> list[Asset]:
        if self.config.read_only:
            self.audit.record(
                "blocked", allowed=False, summary=f"{len(refs)} item(s), read-only mode"
            )
            raise WritesDisabled()
        if len(refs) > self.config.write_batch_max:
            raise TooManyItems(
                f"{len(refs)} items requested; this server allows at most "
                f"{self.config.write_batch_max} per call. Split the work into batches."
            )
        return []

    def _resolve(self, refs: list[str]) -> tuple[list[Asset], list[dict[str, str]]]:
        found: list[Asset] = []
        missing: list[dict[str, str]] = []
        for ref in refs:
            asset = self.lib.get(ref)
            if asset:
                found.append(asset)
            else:
                missing.append({"ref": ref, "reason": "not found in this library"})
        return found, missing

    def _photoslib(self):
        import photoscript

        return photoscript.PhotosLibrary()

    def _apply(
        self,
        refs: list[str],
        action: Callable[[Any, Asset], None],
    ) -> WriteResult:
        self._guard(refs)
        assets, skipped = self._resolve(refs)
        if not assets:
            return WriteResult([], skipped)

        import photoscript

        # Instantiating the library launches Photos.app if it is not running,
        # which every AppleScript write below depends on. The handle itself is
        # not needed: writes address photos by uuid.
        self._photoslib()
        changed: list[str] = []
        for asset in assets:
            try:
                photo = photoscript.Photo(asset.uuid)
                action(photo, asset)
                changed.append(asset.uuid)
            except Exception as exc:
                skipped.append({"ref": asset.uuid, "reason": str(exc)})
        if changed:
            # The cached index is now stale for these assets.
            self.lib.load(force=True)
        return WriteResult(changed, skipped)

    # ------------------------------------------------------------------ tools

    def set_favorite(self, refs: list[str], favorite: bool = True) -> dict[str, Any]:
        res = self._apply(refs, lambda photo, _a: setattr(photo, "favorite", favorite))
        action = "favorite" if favorite else "unfavorite"
        self.audit.record(action, allowed=True, summary=f"{len(res.changed)} item(s)")
        return res.as_dict(action, favorite=favorite)

    def set_title(self, ref: str, title: str) -> dict[str, Any]:
        res = self._apply([ref], lambda photo, _a: setattr(photo, "title", title))
        return res.as_dict("set_title", title=title)

    def set_description(self, ref: str, description: str) -> dict[str, Any]:
        res = self._apply([ref], lambda photo, _a: setattr(photo, "description", description))
        return res.as_dict("set_description", description=description)

    def add_keywords(self, refs: list[str], keywords: list[str]) -> dict[str, Any]:
        def action(photo: Any, _a: Asset) -> None:
            existing = list(photo.keywords or [])
            photo.keywords = existing + [k for k in keywords if k not in existing]

        res = self._apply(refs, action)
        return res.as_dict("add_keywords", keywords=keywords)

    def add_to_album(self, album: str, refs: list[str]) -> dict[str, Any]:
        self._guard(refs)

        # Resolve before touching Photos.app. Launching Photos is a visible,
        # slow side effect, and doing it for a call that turns out to have
        # nothing to add is both surprising and a good way to make the test
        # suite depend on a running Photos.
        assets, skipped = self._resolve(refs)
        if not assets and refs:
            return WriteResult([], skipped).as_dict("add_to_album", album=album)

        import photoscript

        pl = self._photoslib()
        target = None
        for existing in pl.albums():
            if existing.name == album:
                target = existing
                break
        created = target is None
        if target is None:
            target = pl.create_album(album)

        changed: list[str] = []
        for asset in assets:
            try:
                target.add([photoscript.Photo(asset.uuid)])
                changed.append(asset.uuid)
            except Exception as exc:
                skipped.append({"ref": asset.uuid, "reason": str(exc)})
        if changed:
            self.lib.load(force=True)
        return WriteResult(changed, skipped).as_dict(
            "add_to_album", album=album, album_created=created
        )

    def archive(self, refs: list[str], confirm: bool = False) -> dict[str, Any]:
        """The closest thing to delete that macOS permits a script to do.

        This is the only tool here that asks. Everything else it can do is one
        click to undo in Photos, and confirming every write teaches a model to
        pass `confirm` reflexively, which is exactly what must not happen on the
        one action a user reads as deletion.
        """
        if not confirm:
            self.audit.record(
                "archive", allowed=False, summary=f"{len(refs)} item(s), unconfirmed"
            )
            return {
                "action": "archive",
                "confirmed": False,
                "would_archive": len(refs),
                "album": self.config.archive_album,
                "message": (
                    f"Not done yet. This moves {len(refs)} item(s) out of the main view and "
                    f"into the album \"{self.config.archive_album}\". Call again with "
                    f"confirm=true to proceed."
                ),
            }
        out = self.add_to_album(self.config.archive_album, refs)
        out["action"] = "archive"
        out["confirmed"] = True
        self.audit.record(
            "archive", allowed=True, summary=f"{out.get('changed', 0)} item(s) archived"
        )
        out["note"] = (
            f"macOS does not allow any app to delete photos by script. These were moved "
            f"into the album \"{self.config.archive_album}\" instead. To remove them for "
            f"real, open that album in Photos and delete them there."
        )
        return out
