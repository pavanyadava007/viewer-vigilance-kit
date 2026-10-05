"""Common incident schema shared by all sources."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Incident:
    source: str  # FDA_MAUDE | FDA_RECALL | BFARM_FSN
    id: str
    date: str  # ISO yyyy-mm-dd
    manufacturer: str
    product: str
    product_code: str  # FDA product code or BfArM Produktgruppe
    event_type: str
    text: str
    url: str
    extra: dict = field(default_factory=dict)  # source-specific fields (weak labels etc.)
    tags: list[str] = field(default_factory=list)
    relevant: bool = False

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.id}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["uid"] = self.uid
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Incident:
        d = {k: v for k, v in d.items() if k != "uid"}
        return cls(**d)


def dedupe(items: list[Incident]) -> list[Incident]:
    """Keep the first incident per uid, preserve order."""
    seen: set[str] = set()
    out: list[Incident] = []
    for it in items:
        if it.uid in seen:
            continue
        seen.add(it.uid)
        out.append(it)
    return out


def save_jsonl(items: list[Incident], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(it.to_dict(), ensure_ascii=False) + "\n")


def load_jsonl(path: Path) -> list[Incident]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [Incident.from_dict(json.loads(line)) for line in fh if line.strip()]
