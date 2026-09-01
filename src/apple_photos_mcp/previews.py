"""Turning assets into small images the model can actually look at.

Search returns candidates, not answers. A ranked list of filenames is a guess
until something looks at the pixels, so this module renders a downscaled preview
and hands it back through MCP as an image the model sees directly.

Two things make this harder than it sounds:

1. Most assets in a modern library are **not on the Mac**. iCloud keeps the
   originals in the cloud and leaves a thumbnail behind. In the library this was
   built against, 36,996 of 37,129 assets had no local file.
2. Apple's own thumbnails live inside the library bundle as ``derivatives``.
   Reading one is instant and needs no network, which makes it the right source
   for "show me what this is" even when the original is a 48 MP HEIC in iCloud.

So previews come from the derivative when there is one, and fall back to the
original only when there is not.
"""

from __future__ import annotations

import base64
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .library import Asset, PhotosLibrary


@dataclass
class Preview:
    uuid: str
    filename: str
    path: Path | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.path is not None and self.path.exists()


def _sips_resize(src: Path, dst: Path, px: int) -> bool:
    """Resize with ``sips``, which ships with macOS. No Pillow dependency, and it
    reads HEIC, RAW and video posters that Pillow would refuse."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(
            ["sips", "-s", "format", "jpeg", "-Z", str(px), str(src), "--out", str(dst)],
            capture_output=True,
            timeout=60,
            check=False,  # a failed resize is reported, not raised
        )
        return r.returncode == 0 and dst.exists()
    except (OSError, subprocess.SubprocessError):
        return False


def _derivative_for(lib_path: Path, uuid: str) -> Path | None:
    """Apple files derivatives under resources/derivatives/<first hex char>/.

    The layout is not a public contract, so this is best-effort: a miss simply
    falls through to the original.
    """
    base = lib_path / "resources" / "derivatives"
    if not base.is_dir():
        return None
    candidates: list[Path] = []
    shard = base / uuid[0].upper()
    for folder in (shard, base):
        if not folder.is_dir():
            continue
        try:
            candidates.extend(p for p in folder.glob(f"{uuid}*") if p.is_file())
        except OSError:
            continue
        if candidates:
            break
    if not candidates:
        return None

    # Prefer a real image over a .THM video stub, then take the largest of
    # those, Photos writes several sizes per asset and the biggest is the one
    # worth looking at.
    def rank(p: Path) -> tuple[int, int]:
        is_image = p.suffix.lower() in {".jpeg", ".jpg", ".heic", ".png"}
        return (1 if is_image else 0, p.stat().st_size)

    return max(candidates, key=rank)


class PreviewRenderer:
    def __init__(self, config: Config, lib: PhotosLibrary):
        self.config = config
        self.lib = lib

    def render(self, asset: Asset, px: int | None = None) -> Preview:
        px = px or self.config.preview_px
        out = self.config.preview_dir / f"{asset.uuid}-{px}.jpg"
        if out.exists():
            return Preview(asset.uuid, asset.filename, out)

        lib_path = self.lib._library_path()
        source = _derivative_for(lib_path, asset.uuid)

        if source is None:
            # No derivative. Fall back to the original, which only exists when
            # the asset has been downloaded from iCloud.
            original = self._original_path(asset)
            if original is None:
                return Preview(
                    asset.uuid,
                    asset.filename,
                    None,
                    error=(
                        "No local preview. This asset lives in iCloud and has not been "
                        "downloaded to this Mac. Open it in Photos once, or run "
                        "export_originals, to pull it down."
                    ),
                )
            source = original

        if not _sips_resize(source, out, px):
            return Preview(asset.uuid, asset.filename, None, error="Could not render a preview.")
        return Preview(asset.uuid, asset.filename, out)

    def _original_path(self, asset: Asset) -> Path | None:
        if not asset.local:
            return None
        import osxphotos

        db = osxphotos.PhotosDB(str(self.lib._library_path()))
        for p in db.photos(uuid=[asset.uuid]):
            if p.path:
                return Path(p.path)
        return None

    @staticmethod
    def as_base64(path: Path) -> str:
        return base64.b64encode(path.read_bytes()).decode("ascii")
