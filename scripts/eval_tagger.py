"""Evaluate the rule tagger against agency-assigned weak labels.

BfArM: relevance flag vs Produktgruppe (labels A and B in vigil/weak_labels.yaml).
MAUDE: per-category tags (from narrative text only) vs FDA product_problems terms.
Split: deterministic 50/50 by sha1(uid); "dev" was used while writing the rules,
"test" was not looked at. Writes results/tagger_eval.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml

from vigil.schema import load_jsonl
from vigil.tagger import Rules

ROOT = Path(__file__).resolve().parents[1]


def split_of(uid: str) -> str:
    return "dev" if int(hashlib.sha1(uid.encode()).hexdigest(), 16) % 2 == 0 else "test"


def prf(pred: list[bool], gold: list[bool]) -> dict:
    tp = sum(p and g for p, g in zip(pred, gold, strict=True))
    fp = sum(p and not g for p, g in zip(pred, gold, strict=True))
    fn = sum(g and not p for p, g in zip(pred, gold, strict=True))
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else None
    r3 = lambda x: None if x is None else round(x, 3)  # noqa: E731
    return {
        "n": len(gold),
        "positives": sum(gold),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": r3(prec),
        "recall": r3(rec),
        "f1": r3(f1),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(ROOT / "data/corpus.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "results/tagger_eval.json"))
    ap.add_argument("--show-errors", choices=["dev"], help="print dev-split errors only")
    args = ap.parse_args()
    rules = Rules.load()
    wl = yaml.safe_load((ROOT / "vigil/weak_labels.yaml").read_text(encoding="utf-8"))
    items = load_jsonl(Path(args.corpus))
    out: dict = {"corpus": args.corpus.split("/")[-1], "bfarm": {}, "maude": {}}

    b = [i for i in items if i.source == "BFARM_FSN"]
    for lab, prefixes in wl["bfarm"].items():
        for sp in ("dev", "test", "all"):
            sel = [i for i in b if sp == "all" or split_of(i.uid) == sp]
            gold = [i.product_code.startswith(tuple(prefixes)) for i in sel]
            pred = [rules.is_relevant(f"{i.product} {i.text}") for i in sel]
            out["bfarm"].setdefault(lab, {})[sp] = prf(pred, gold)
            if args.show_errors == sp == "dev" and lab == "software_or_imaging":
                for i, p, g in zip(sel, pred, gold, strict=True):
                    if p != g:
                        print("FP" if p else "FN", i.product_code[:40], "|", i.text[:110])
    out["bfarm"]["date_range"] = [min(i.date for i in b), max(i.date for i in b)]

    m = [i for i in items if i.source == "FDA_MAUDE"]
    mapping = wl["maude_problem_to_category"]
    out["maude"]["n_reports"] = len(m)
    out["maude"]["n_with_text"] = sum(1 for i in m if i.text.strip())
    out["maude"]["date_range"] = [min(i.date for i in m), max(i.date for i in m)]
    for sp in ("dev", "test", "all"):
        sel = [i for i in m if sp == "all" or split_of(i.uid) == sp]
        tags = [set(rules.categorize(i.text)) for i in sel]
        probs = [set(i.extra.get("product_problems", [])) for i in sel]
        per = {}
        for cat, terms in mapping.items():
            gold = [bool(p & set(terms)) for p in probs]
            pred = [cat in t for t in tags]
            per[cat] = prf(pred, gold)
            if args.show_errors == sp == "dev":
                for i, p, g in zip(sel, pred, gold, strict=True):
                    if p != g:
                        print("FP" if p else "FN", cat, "|", i.text[:140])
        tot = {k: sum(per[c][k] for c in per) for k in ("tp", "fp", "fn")}
        micro = prf([], [])
        micro.update(tot)
        p = tot["tp"] / (tot["tp"] + tot["fp"]) if tot["tp"] + tot["fp"] else None
        r = tot["tp"] / (tot["tp"] + tot["fn"]) if tot["tp"] + tot["fn"] else None
        micro["precision"] = round(p, 3) if p is not None else None
        micro["recall"] = round(r, 3) if r is not None else None
        micro["n"] = len(sel)
        micro["positives"] = tot["tp"] + tot["fn"]
        del micro["f1"]
        out["maude"][sp] = {"per_category": per, "micro": micro}
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    for lab in wl["bfarm"]:
        print("bfarm", lab, out["bfarm"][lab]["test"])
    print("maude micro test", out["maude"]["test"]["micro"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
