"""Read-only mode and the write audit log.

The shape is the one every server here uses: writes work, the irreversible ones
ask, and one environment variable removes writes entirely for an unattended
agent.

Writes are not off by default. A server that gates every write behind a flag
produces one of two outcomes: the user gives up, or the user pastes the flag
into their config once and never thinks about it again. The second is common and
is worse than no gate, because it looks like a safeguard while being permanently
disabled.
"""

from __future__ import annotations

import json
import time
from typing import Any

from .config import Config


class AuditLog:
    """One JSON line per attempted write.

    A failed audit write must never turn a successful action into a reported
    error. This is a record, not a control, so every failure here is swallowed.
    """

    def __init__(self, config: Config):
        self.path = config.audit_log

    def record(self, action: str, *, allowed: bool, summary: str, **extra: Any) -> None:
        if self.path is None:
            return
        line = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "action": action,
            "allowed": allowed,
            "summary": summary,
            **extra,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, default=str) + "\n")
        except OSError:
            pass


#: MCP tool annotations, so a client can decide what to auto-approve.
#: `openWorldHint` is false throughout: nothing here leaves the machine.
READ_ONLY_TOOL = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

REVERSIBLE_WRITE = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

DESTRUCTIVE_WRITE = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": False,
    "openWorldHint": False,
}
