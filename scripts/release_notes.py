"""Release notes from conventional commits between the previous tag and HEAD."""

from __future__ import annotations

import argparse
import re
import subprocess

GROUPS = [
    ("feat", "Features"),
    ("fix", "Fixes"),
    ("test", "Tests"),
    ("ci", "CI and release"),
    ("docs", "Documentation"),
    ("refactor", "Refactoring"),
    ("chore", "Chores"),
]
PAT = re.compile(r"^(\w+)(\([^)]*\))?(!)?:\s*(.+)$")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    prev = git("describe", "--tags", "--abbrev=0", f"{a.tag}^") if git("tag") else ""
    rng = f"{prev}..{a.tag}" if prev else a.tag
    log = git("log", "--no-merges", "--format=%h %s", rng).splitlines()
    buckets: dict[str, list[str]] = {k: [] for k, _ in GROUPS}
    other: list[str] = []
    for line in log:
        sha, _, subj = line.partition(" ")
        m = PAT.match(subj)
        entry = f"- {m.group(4) if m else subj} ({sha})"
        if m and m.group(1) in buckets:
            buckets[m.group(1)].append(entry)
        else:
            other.append(entry)
    out = [f"# {a.tag}", "", f"Changes since {prev or 'the first commit'}.", ""]
    for key, title in GROUPS:
        if buckets[key]:
            out += [f"## {title}", "", *buckets[key], ""]
    if other:
        out += ["## Other", "", *other, ""]
    out += [
        "Attached: release-candidate test report, traceability matrix, planted-defect "
        "study and a sample vigilance digest.",
        "",
    ]
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
