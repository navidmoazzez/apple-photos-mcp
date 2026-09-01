"""Entry point: ``apple-photos-mcp`` (stdio) and ``apple-photos-mcp doctor``."""

from __future__ import annotations

import json
import logging
import sys

from .config import Config


def main() -> int:
    # stderr only. Anything on stdout corrupts the JSON-RPC stream.
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    args = sys.argv[1:]
    config = Config.from_env()

    if args and args[0] in {"-v", "--version"}:
        from . import __version__

        print(__version__)
        return 0

    if args and args[0] == "doctor":
        from . import doctor as doctor_mod
        from .library import PhotosLibrary

        report = doctor_mod.run(config, PhotosLibrary(config))
        print(json.dumps(report, indent=2, default=str))
        return 0 if report["ok"] else 1

    from .server import build_server

    build_server(config).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
