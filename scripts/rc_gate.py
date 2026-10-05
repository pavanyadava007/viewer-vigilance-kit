"""Release-candidate gate. Runs every check a release needs and writes a test report.

Checks: lint, format, full test suite (JUnit XML), requirement traceability,
planted-defect study (every defect must be caught by the full suite), version
consistency (and tag match when run on a v* tag). Writes reports/rc/rc_report.md and
reports/rc/rc_gate.json. Exit code 0 only if every check passes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/rc"
PY = sys.executable


def sh(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})
        print(("PASS " if ok else "FAIL ") + name + ": " + detail)

    rc, out = sh([PY, "-m", "ruff", "check", "."])
    add("ruff check", rc == 0, out.splitlines()[-1] if out else "")
    rc, out = sh([PY, "-m", "ruff", "format", "--check", "."])
    add("ruff format --check", rc == 0, out.splitlines()[-1] if out else "")

    junit = OUT / "junit.xml"
    rc, out = sh([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={junit}"])
    suite = ET.parse(junit).getroot()
    suite = suite if suite.tag == "testsuite" else suite.find("testsuite")
    stats = {k: int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped")}
    add("pytest (all tiers + vigil)", rc == 0, json.dumps(stats))

    rc, out = sh([PY, "scripts/traceability.py", "--md", str(OUT / "traceability.md")])
    add("traceability", rc == 0, out.splitlines()[-1] if out else "")

    mut = OUT / "mutants.json"
    rc, out = sh([PY, "scripts/run_mutants.py", "--out", str(mut)])
    if rc == 0:
        m = json.loads(mut.read_text())
        ok = m["caught"]["unit_golden"] == m["n_defects"]
        add("planted defects caught", ok, f"{m['caught']['unit_golden']}/{m['n_defects']}")
    else:
        add("planted defects caught", False, out.splitlines()[-1] if out else "run failed")

    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    sys.path.insert(0, str(ROOT))
    import viewer
    import vigil

    same = version == viewer.__version__ == vigil.__version__
    ref = os.environ.get("GITHUB_REF_NAME", "")
    tag_ok = not re.match(r"^v\d", ref) or ref == f"v{version}"
    add("version consistency", same and tag_ok, f"pyproject {version}, tag '{ref or '-'}'")

    ok = all(c["ok"] for c in checks)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    _, commit = sh(["git", "rev-parse", "--short", "HEAD"])
    report = {"version": version, "commit": commit, "time": now, "passed": ok, "checks": checks}
    (OUT / "rc_gate.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        f"# Release candidate test report v{version}",
        "",
        f"Commit `{commit}`, generated {now}. Verdict: **{'PASS' if ok else 'FAIL'}**.",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
        *[f"| {c['check']} | {'PASS' if c['ok'] else 'FAIL'} | {c['detail']} |" for c in checks],
        "",
        "## Traceability",
        "",
        (OUT / "traceability.md").read_text() if (OUT / "traceability.md").exists() else "n/a",
        "Engineering evidence for a portfolio project. Not a regulatory document.",
        "",
    ]
    (OUT / "rc_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("RC GATE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
