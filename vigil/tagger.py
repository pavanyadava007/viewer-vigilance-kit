"""Rule-based relevance flag and category tagger (rules in rules.yaml)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .schema import Incident

RULES_PATH = Path(__file__).with_name("rules.yaml")


@dataclass
class Rules:
    relevance: list[re.Pattern]
    categories: dict[str, list[re.Pattern]]

    @classmethod
    def load(cls, path: Path | str = RULES_PATH) -> Rules:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        rel = [re.compile(p, re.I) for p in raw["relevance"]]
        cats = {k: [re.compile(p, re.I) for p in v] for k, v in raw["categories"].items()}
        return cls(rel, cats)

    def is_relevant(self, text: str) -> bool:
        return any(p.search(text) for p in self.relevance)

    def categorize(self, text: str) -> list[str]:
        return [c for c, pats in self.categories.items() if any(p.search(text) for p in pats)]

    def explain(self, text: str) -> dict[str, list[str]]:
        """Which patterns fired, per category (for transparent review)."""
        out = {}
        for c, pats in {"relevance": self.relevance, **self.categories}.items():
            hits = [p.pattern for p in pats if p.search(text)]
            if hits:
                out[c] = hits
        return out


def tag(
    items: list[Incident], rules: Rules | None = None, bfarm_groups: tuple[str, ...] = ()
) -> list[Incident]:
    """Set `relevant` and `tags` in place.

    FDA items are already selected by imaging-software product codes, so they are relevant.
    BfArM items are relevant if the agency's Produktgruppe starts with one of
    `bfarm_groups` or the text rules match (the rules catch e.g. MR systems that BfArM
    files under "Elektro-Magnetische Felder").
    """
    rules = rules or Rules.load()
    for it in items:
        text = f"{it.product} {it.text}"
        by_group = bool(bfarm_groups) and it.product_code.startswith(bfarm_groups)
        it.relevant = it.source.startswith("FDA_") or by_group or rules.is_relevant(text)
        it.tags = rules.categorize(it.text)
    return items
