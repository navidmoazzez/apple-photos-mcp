"""Configuration, resolved once from the environment.

Settings are environment variables, not CLI flags, because a user editing a
client config is already inside a JSON `env` block and flags mean editing
`args` separately.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_PREFIX = "APPLE_PHOTOS_"


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(ENV_PREFIX + name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(ENV_PREFIX + name, "").strip())
    except (TypeError, ValueError):
        return default


def _path(name: str) -> Path | None:
    raw = os.environ.get(ENV_PREFIX + name)
    return Path(raw).expanduser() if raw else None


@dataclass(frozen=True)
class Config:
    """Resolved server configuration."""

    #: Explicit .photoslibrary path. ``None`` means "whichever Photos opened last".
    library: Path | None = None

    #: Removes every write tool from the tool list rather than erroring when one
    #: is called. A model cannot call a tool it cannot see, and an error is an
    #: invitation to retry differently. This is the real defense for an agent
    #: working unattended.
    read_only: bool = False

    #: One JSON line per attempted write, allowed and blocked alike.
    audit_log: Path | None = None

    #: Where ``export_originals`` writes when the caller does not name a folder.
    export_dir: Path = Path.home() / "Downloads" / "Photos Exports"

    #: Where ``look_at_photos`` caches the previews it hands to the model.
    preview_dir: Path = Path.home() / ".apple-photos-mcp" / "previews"

    #: Longest edge, in pixels, of a preview. Small enough to stay cheap in context.
    preview_px: int = 640

    #: Most items a single ``look_at_photos`` call will render.
    preview_max: int = 8

    #: Most items any single write touches. A typo should not restructure a library.
    write_batch_max: int = 100

    #: Album that ``archive_photos`` moves items into. Apple forbids scripted deletion.
    archive_album: str = "Archived by Claude"

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            library=_path("LIBRARY"),
            read_only=_flag("READ_ONLY"),
            audit_log=_path("AUDIT_LOG"),
            export_dir=_path("EXPORT_DIR") or cls.export_dir,
            preview_dir=_path("PREVIEW_DIR") or cls.preview_dir,
            preview_px=_int("PREVIEW_PX", cls.preview_px),
            preview_max=_int("PREVIEW_MAX", cls.preview_max),
            write_batch_max=_int("WRITE_BATCH_MAX", cls.write_batch_max),
            archive_album=os.environ.get(ENV_PREFIX + "ARCHIVE_ALBUM") or cls.archive_album,
        )
