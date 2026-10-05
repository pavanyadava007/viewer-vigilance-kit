"""Print the requirement -> test traceability matrix; exit 1 on gaps.

Fails if a requirement has no test, or names a test that pytest does not collect.
Writes results/traceability.json and (with --md) a Markdown table.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def collected() -> tuple[set[str], int]:
    """Test function ids (parametrisation dropped) and the number of collected test items."""
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    items = [line.strip() for line in p.stdout.splitlines() if "::" in line]
    return {i.split("[")[0] for i in items}, len(items)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", help="write Markdown matrix to this path")
    args = ap.parse_args()
    reqs = yaml.safe_load((ROOT / "requirements.yaml").read_text(encoding="utf-8"))["requirements"]
    have, n_items = collected()
    rows, problems = [], []
    for r in reqs:
        tests = r.get("tests") or []
        missing = [t for t in tests if t not in have]
        if not tests:
            problems.append(f"{r['id']}: no test")
        for t in missing:
            problems.append(f"{r['id']}: test not found: {t}")
        rows.append({"id": r["id"], "text": r["text"], "tests": tests, "missing": missing})
    all_traced = {t for r in reqs for t in r.get("tests") or []}
    untraced = sorted(t for t in have if t not in all_traced)
    out = {
        "n_requirements": len(reqs),
        "n_test_functions": len(have),
        "n_test_items": n_items,
        "n_tests_traced": len(all_traced & have),
        "untraced_tests": untraced,
        "problems": problems,
        "ok": not problems,
    }
    (ROOT / "results/traceability.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    lines = ["| Requirement | Tests | Status |", "|---|---:|---|"]
    for r in rows:
        status = "OK" if r["tests"] and not r["missing"] else "GAP"
        lines.append(f"| {r['id']} | {len(r['tests'])} | {status} |")
        print(f"{r['id']:8} {len(r['tests']):2d} tests  {status:3}  {r['text'][:70]}")
    if args.md:
        Path(args.md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(reqs)} requirements, {out['n_tests_traced']}/{len(have)} test functions traced")
    for p in problems:
        print("PROBLEM:", p)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
