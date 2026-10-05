"""Run state: remembers which incident uids were already reported."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .schema import Incident


class State:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.seen: set[str] = set()
        self.last_run: str | None = None
        if self.path.exists():
            d = json.loads(self.path.read_text(encoding="utf-8"))
            self.seen = set(d.get("seen", []))
            self.last_run = d.get("last_run")

    def new_items(self, items: list[Incident]) -> list[Incident]:
        return [it for it in items if it.uid not in self.seen]

    def mark(self, items: list[Incident]) -> None:
        self.seen.update(it.uid for it in items)

    def save(self, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        self.last_run = now.isoformat(timespec="seconds")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"last_run": self.last_run, "seen": sorted(self.seen)}
        self.path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
