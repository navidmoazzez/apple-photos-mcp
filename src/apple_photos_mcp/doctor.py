"""Self-diagnosis.

Almost every failure with a Photos integration is one of four things, and all
four are invisible from inside a chat window: the wrong OS, a missing Full Disk
Access grant, a library that cannot be found, or writes being off when the user
expected them on. ``doctor`` names which one it is and what to click.
"""

from __future__ import annotations

import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from .config import Config
from .library import PhotosLibrary


def _check(name: str, ok: bool, detail: str, fix: str = "") -> dict[str, Any]:
    out = {"check": name, "ok": ok, "detail": detail}
    if not ok and fix:
        out["fix"] = fix
    return out


def run(config: Config, lib: PhotosLibrary) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    is_mac = sys.platform == "darwin"
    checks.append(
        _check(
            "macOS",
            is_mac,
            f"{platform.system()} {platform.mac_ver()[0] or platform.release()}",
            "Apple Photos exists only on macOS. This server cannot run anywhere else.",
        )
    )

    checks.append(
        _check(
            "python",
            sys.version_info >= (3, 11),
            f"Python {platform.python_version()}",
            "Python 3.11 or newer is required.",
        )
    )

    checks.append(
        _check(
            "sips",
            shutil.which("sips") is not None,
            "sips is used to render previews and ships with macOS",
            "sips is missing, which should be impossible on a healthy macOS install.",
        )
    )

    # Locating the library.
    lib_path: Path | None = None
    try:
        lib_path = lib._library_path()
        found = lib_path.exists()
        checks.append(
            _check(
                "library found",
                found,
                str(lib_path),
                "Open Photos once so macOS records a library path, or set "
                "APPLE_PHOTOS_LIBRARY to a .photoslibrary folder.",
            )
        )
    except Exception as exc:
        checks.append(
            _check(
                "library found",
                False,
                str(exc),
                "Set APPLE_PHOTOS_LIBRARY to your .photoslibrary path.",
            )
        )

    # Full Disk Access is the single most common failure, and it presents as a
    # permission error on the library's SQLite rather than as anything obvious.
    readable = False
    detail = "not attempted"
    if lib_path and lib_path.exists():
        db = lib_path / "database" / "Photos.sqlite"
        try:
            with open(db, "rb") as fh:
                fh.read(16)
            readable = True
            detail = "library database is readable"
        except PermissionError:
            detail = "permission denied reading the library database"
        except FileNotFoundError:
            detail = "library database not found at the expected path"
        except OSError as exc:
            detail = str(exc)
    checks.append(
        _check(
            "full disk access",
            readable,
            detail,
            "Give the app that runs this server Full Disk Access: System Settings > "
            "Privacy & Security > Full Disk Access. For Claude Desktop add Claude; for "
            "a terminal add Terminal or iTerm. Then fully quit and reopen it.",
        )
    )

    # Index.
    if readable:
        try:
            stats = lib.stats()
            checks.append(
                _check(
                    "index",
                    True,
                    f"{stats['total']} assets indexed "
                    f"({stats['with_ml_labels']} with ML labels, "
                    f"{stats['with_text_in_image']} with readable text)",
                )
            )
            if stats["not_downloaded_to_mac"]:
                checks.append(
                    _check(
                        "icloud",
                        True,
                        f"{stats['not_downloaded_to_mac']} of {stats['total']} assets live "
                        f"in iCloud and have no full-size local file. Previews still work "
                        f"(they come from Apple's own thumbnails); exporting an original "
                        f"downloads it first and is slower.",
                    )
                )
        except Exception as exc:
            checks.append(
                _check("index", False, str(exc), "Run doctor again after opening Photos once.")
            )

    checks.append(
        _check(
            "writes",
            True,
            "read-only (APPLE_PHOTOS_READ_ONLY is set)" if config.read_only else "enabled",
        )
    )
    checks[-1]["note"] = (
        "Write tools are hidden in read-only mode. Unset APPLE_PHOTOS_READ_ONLY to "
        "restore them."
        if config.read_only
        else "Organizing works. archive_photos asks for confirm first, and nothing "
        "can permanently delete a photo."
    )
    if config.audit_log:
        checks.append(_check("audit log", True, str(config.audit_log)))

    failed = [c for c in checks if not c["ok"]]
    return {
        "ok": not failed,
        "summary": "All checks passed." if not failed else f"{len(failed)} check(s) failed.",
        "checks": checks,
    }
