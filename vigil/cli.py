"""Command line: `vigil run` (weekly monitor) and `vigil corpus` (backfill for evaluation)."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import yaml

from . import bfarm, fda
from .digest import render_markdown, write_csv
from .http import CachedClient
from .schema import Incident, dedupe, save_jsonl
from .state import State
from .tagger import tag

CONFIG = Path(__file__).with_name("config.yaml")


def load_config(path: Path | str = CONFIG) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _summary(items: list[Incident]) -> dict:
    out: dict = {}
    for it in items:
        s = out.setdefault(it.source, {"n": 0, "min_date": "9999", "max_date": "0000"})
        s["n"] += 1
        if it.date:
            s["min_date"] = min(s["min_date"], it.date)
            s["max_date"] = max(s["max_date"], it.date)
    return out


def cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    client = CachedClient(args.cache, cfg["http"]["min_interval_s"], offline=args.offline)
    codes = list(cfg["fda"]["product_codes"])
    today = date.fromisoformat(args.today) if args.today else date.today()
    cap = cfg["fda"]["max_records_per_code"]
    maude, m_meta = fda.fetch_maude(client, codes, args.maude_days, cap, today)
    recalls, r_meta = fda.fetch_recalls(client, codes, args.recall_days, cap, today)
    fsn = bfarm.fetch_rss(client, cfg["bfarm"]["rss_url"], cfg["bfarm"]["fetch_details"])
    items = tag(dedupe(maude + recalls + fsn), bfarm_groups=tuple(cfg["bfarm"]["relevant_groups"]))
    state = State(args.state)
    new = state.new_items(items)
    out = Path(args.out)
    stamp = today.isoformat()
    period = (
        f"MAUDE date_received {m_meta['from']} to {m_meta['to']}; recalls initiated "
        f"{r_meta['from']} to {r_meta['to']}; BfArM RSS (latest {len(fsn)} notices). "
        f"Only items not reported in an earlier run (state: {state.last_run or 'first run'})."
    )
    md = render_markdown(new, f"Viewer vigilance digest {stamp}", period)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"digest-{stamp}.md").write_text(md, encoding="utf-8")
    (out / "latest.md").write_text(md, encoding="utf-8")
    write_csv(new, out / f"digest-{stamp}.csv")
    write_csv(new, out / "latest.csv")
    run_meta = {
        "date": stamp,
        "fetched": _summary(items),
        "new": _summary(new),
        "new_relevant": sum(1 for i in new if i.relevant),
        "maude_query": m_meta,
        "recall_query": r_meta,
        "http": {"network": client.n_network, "cache": client.n_cache},
    }
    (out / "latest.json").write_text(json.dumps(run_meta, indent=2), encoding="utf-8")
    if not args.dry_run:
        state.mark(items)
        state.save()
    print(json.dumps({k: run_meta[k] for k in ("fetched", "new", "new_relevant")}, indent=1))
    return 0


def cmd_corpus(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    client = CachedClient(args.cache, cfg["http"]["min_interval_s"], ttl_s=7 * 86400)
    codes = list(cfg["fda"]["product_codes"])
    today = date.fromisoformat(args.today) if args.today else date.today()
    cap = cfg["fda"]["max_records_per_code"]
    maude, m_meta = fda.fetch_maude(client, codes, cfg["fda"]["maude_days"], cap, today)
    recalls, r_meta = fda.fetch_recalls(client, codes, cfg["fda"]["recall_days"], cap, today)
    fsn = bfarm.fetch_list(client, cfg["bfarm"]["list_url"], cfg["bfarm"]["list_pages"])
    items = tag(dedupe(maude + recalls + fsn), bfarm_groups=tuple(cfg["bfarm"]["relevant_groups"]))
    save_jsonl(items, Path(args.output))
    summary = {
        "run_date": today.isoformat(),
        "maude_query": m_meta,
        "recall_query": r_meta,
        "bfarm_list_pages": cfg["bfarm"]["list_pages"],
        "per_source": _summary(items),
        "duplicates_removed": len(maude) + len(recalls) + len(fsn) - len(items),
    }
    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary["per_source"], indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vigil", description=__doc__)
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--cache", default="data/raw")
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="weekly monitor: fetch, tag, report only new items")
    r.add_argument("--state", default="data/state.json")
    r.add_argument("--out", default="reports")
    r.add_argument("--maude-days", type=int, default=90)
    r.add_argument("--recall-days", type=int, default=120)
    r.add_argument("--offline", action="store_true", help="use cached responses only")
    r.add_argument("--dry-run", action="store_true", help="do not update the state file")
    c = sub.add_parser("corpus", help="backfill corpus used by the tagger evaluation")
    c.add_argument("--output", default="data/corpus.jsonl")
    c.add_argument("--summary", default="results/fetch_summary.json")
    args = ap.parse_args(argv)
    return cmd_run(args) if args.cmd == "run" else cmd_corpus(args)


if __name__ == "__main__":
    raise SystemExit(main())
