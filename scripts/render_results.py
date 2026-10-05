"""Render results/*.json into Markdown tables and splice them into README.md.

Every number shown in the README comes from a JSON file written by a script in this repo.
Sections are replaced between <!-- BEGIN name --> and <!-- END name --> markers.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"


def _load(name: str) -> dict:
    return json.loads((RES / name).read_text(encoding="utf-8"))


def _f(x) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def product_codes() -> str:
    d = _load("product_codes.json")
    rows = ["| Code | Official name (openFDA classification) | Regulation | Class | Verified |"]
    rows.append("|---|---|---|---|---|")
    for c in d["chosen"]:
        rows.append(
            f"| {c['product_code']} | {c['device_name']} | 21 CFR {c['regulation_number']} | "
            f"{c['device_class']} | {'yes' if c['name_matches_config'] else 'NO'} |"
        )
    return "\n".join(rows)


def fetch() -> str:
    d = _load("fetch_summary.json")
    mq, rq = d["maude_query"], d["recall_query"]
    codes = [k for k in mq if len(k) == 3 and k.isupper()]
    rows = [
        f"Corpus fetched on {d['run_date']}.",
        "",
        "| Source | Query window | Items | Item dates |",
        "|---|---|---:|---|",
    ]
    ps = d["per_source"]
    for src, q, lab in (
        ("FDA_MAUDE", mq, "date_received"),
        ("FDA_RECALL", rq, "event_date_initiated"),
    ):
        s = ps.get(src, {"n": 0, "min_date": "-", "max_date": "-"})
        rows.append(
            f"| {src} | {lab} {q['from']} to {q['to']} | {s['n']} | "
            f"{s['min_date']} to {s['max_date']} |"
        )
    b = ps["BFARM_FSN"]
    rows.append(
        f"| BFARM_FSN | list pages 1-{d['bfarm_list_pages']} (50 per page) | {b['n']} | "
        f"{b['min_date']} to {b['max_date']} |"
    )
    rows += ["", "| Product code | MAUDE reports | Recall records |", "|---|---:|---:|"]
    for c in codes:
        rows.append(f"| {c} | {mq[c]['fetched']} | {rq[c]['fetched']} |")
    rows += ["", f"Duplicates removed: {d['duplicates_removed']}."]
    return "\n".join(rows)


def tagger() -> str:
    d = _load("tagger_eval.json")
    b = d["bfarm"]
    rows = [
        f"BfArM notices {b['date_range'][0]} to {b['date_range'][1]}; text = notice title "
        "(product + manufacturer).",
        "",
        "| Weak label (agency Produktgruppe) | Split | n | Positives | Precision | Recall | F1 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    names = {
        "imaging": "A: Radiologische Technik",
        "software_or_imaging": "B: A + Med. Datenverarbeitung (Software) + Ultraschalltechnik",
    }
    for lab, title in names.items():
        for sp in ("dev", "test", "all"):
            r = b[lab][sp]
            rows.append(
                f"| {title} | {sp} | {r['n']} | {r['positives']} | {_f(r['precision'])} | "
                f"{_f(r['recall'])} | {_f(r['f1'])} |"
            )
    m = d["maude"]
    rows += [
        "",
        f"MAUDE reports {m['date_range'][0]} to {m['date_range'][1]}: {m['n_reports']} "
        f"reports, {m['n_with_text']} with narrative text. Tagger reads the narrative only; "
        "label = FDA product_problems terms mapped to categories (vigil/weak_labels.yaml).",
        "",
        "| Category | Test positives | Test precision | Test recall | Dev positives | "
        "Dev precision | Dev recall |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for cat, r in m["test"]["per_category"].items():
        dv = m["dev"]["per_category"][cat]
        rows.append(
            f"| {cat} | {r['positives']} | {_f(r['precision'])} | {_f(r['recall'])} | "
            f"{dv['positives']} | {_f(dv['precision'])} | {_f(dv['recall'])} |"
        )
    for sp in ("test", "dev"):
        mi = m[sp]["micro"]
        rows.append(
            f"| **micro, {sp}** | {mi['positives']} | {_f(mi['precision'])} | "
            f"{_f(mi['recall'])} | | | |"
        )
    return "\n".join(rows)


def mutants() -> str:
    d = _load("mutants.json")
    t = d["tests_per_tier"]
    c = d["caught"]
    n = d["n_defects"]
    rows = [
        "| Tier | Tests run | Defects caught | Catch rate |",
        "|---|---:|---:|---:|",
        f"| Smoke only | {t['smoke']} | {c['smoke']}/{n} | {d['catch_rate']['smoke']:.0%} |",
        f"| Smoke + unit | {t['unit']} | {c['unit']}/{n} | {d['catch_rate']['unit']:.0%} |",
        f"| Smoke + unit + golden | {t['unit_golden']} | {c['unit_golden']}/{n} | "
        f"{d['catch_rate']['unit_golden']:.0%} |",
        f"| Golden only (extra view) | {t['golden_only']} | {c['golden_only']}/{n} | "
        f"{d['catch_rate']['golden_only']:.0%} |",
        "",
        "| Planted defect | What it does | Failing tests: smoke / unit tier / full / golden only |",
        "|---|---|---|",
    ]
    for r in d["defects"]:
        rows.append(
            f"| `{r['defect']}` | {r['description']} | {r['failing_tests_smoke']} / "
            f"{r['failing_tests_unit']} / {r['failing_tests_unit_golden']} / "
            f"{r['failing_tests_golden_only']} |"
        )
    return "\n".join(rows)


def tests() -> str:
    tr = _load("traceability.json")
    m = _load("mutants.json")["tests_per_tier"]
    return (
        f"{tr['n_test_items']} collected test items ({tr['n_test_functions']} test functions): "
        f"{m['smoke']} smoke, {m['unit'] - m['smoke']} unit, {m['golden_only']} golden, "
        f"{tr['n_test_items'] - m['unit_golden']} vigilance-monitor tests. "
        f"{tr['n_requirements']} requirements, all traced: {tr['ok']}."
    )


def digest() -> str:
    d = json.loads((ROOT / "reports/sample/digest-sample.json").read_text(encoding="utf-8"))
    rows = [
        f"First run on {d['date']} (empty state, so every item in the window is new).",
        "",
        "| Source | Items | Item dates |",
        "|---|---:|---|",
    ]
    for src, s in d["new"].items():
        rows.append(f"| {src} | {s['n']} | {s['min_date']} to {s['max_date']} |")
    rows.append(f"\nItems flagged viewer/imaging relevant: {d['new_relevant']}.")
    return "\n".join(rows)


SECTIONS = {
    "product_codes": product_codes,
    "fetch": fetch,
    "tagger": tagger,
    "mutants": mutants,
    "tests": tests,
    "digest": digest,
}


def render_all() -> dict[str, str]:
    return {k: f() for k, f in SECTIONS.items()}


def main() -> int:
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    for name, body in render_all().items():
        pat = re.compile(rf"(<!-- BEGIN {name} -->\n).*?(<!-- END {name} -->)", re.S)
        if not pat.search(text):
            print("marker missing:", name)
            continue
        text = pat.sub(lambda m, b=body: m.group(1) + b + "\n" + m.group(2), text)
    readme.write_text(text, encoding="utf-8")
    print("README tables rendered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
