"""Mutation study: switch on each planted viewer defect and see which test tier catches it.

Tiers (cumulative):
  smoke         -m smoke
  unit          -m "smoke or unit"
  unit_golden   -m "smoke or unit or golden"
plus golden_only (-m golden) to show what golden images catch on their own.
A defect is "caught" by a tier if that tier's pytest run fails. A baseline run with no
defect must pass in every tier, otherwise the study is invalid.
Writes results/mutants.json.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from viewer._defects import DEFECTS  # noqa: E402

TIERS = {
    "smoke": "smoke",
    "unit": "smoke or unit",
    "unit_golden": "smoke or unit or golden",
    "golden_only": "golden",  # extra view: golden images without the unit tests
}
TEST_FILES = [
    "tests/test_viewer_smoke.py",
    "tests/test_viewer_unit.py",
    "tests/test_viewer_golden.py",
]


def run(marker: str, defect: str | None) -> dict:
    env = dict(os.environ)
    env.pop("VIEWER_DEFECT", None)
    if defect:
        env["VIEWER_DEFECT"] = defect
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", marker]
    p = subprocess.run(cmd + TEST_FILES, cwd=ROOT, env=env, capture_output=True, text=True)
    tail = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ""
    failed = int(m.group(1)) if (m := re.search(r"(\d+) failed", tail)) else 0
    passed = int(m.group(1)) if (m := re.search(r"(\d+) passed", tail)) else 0
    return {"rc": p.returncode, "failed": failed, "passed": passed}


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results/mutants.json"))
    args = ap.parse_args()
    t0 = time.time()
    baseline = {t: run(m, None) for t, m in TIERS.items()}
    if any(b["rc"] != 0 for b in baseline.values()):
        print("baseline not green:", baseline)
        return 1
    rows = []
    for name, desc in DEFECTS.items():
        res = {t: run(m, name) for t, m in TIERS.items()}
        rows.append(
            {
                "defect": name,
                "description": desc,
                **{f"caught_{t}": r["rc"] != 0 for t, r in res.items()},
                **{f"failing_tests_{t}": r["failed"] for t, r in res.items()},
            }
        )
        print(name, {t: r["failed"] for t, r in res.items()})
    n = len(rows)
    summary = {t: sum(r[f"caught_{t}"] for r in rows) for t in TIERS}
    out = {
        "n_defects": n,
        "tests_per_tier": {t: b["passed"] for t, b in baseline.items()},
        "caught": summary,
        "catch_rate": {t: round(v / n, 3) for t, v in summary.items()},
        "defects": rows,
        "runtime_s": round(time.time() - t0, 1),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("tests_per_tier", "caught", "catch_rate")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
