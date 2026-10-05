"""Build the static Hugging Face Space page (space/index.html + images) from results/*.json."""

from __future__ import annotations

import html
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from render_results import render_all  # noqa: E402

OUT = ROOT / "space"
REPO = "https://github.com/pavanyadava007/viewer-vigilance-kit"


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def md_to_html(md: str) -> str:
    out, table = [], []

    def flush() -> None:
        if not table:
            return
        rows = [r.strip().strip("|").split("|") for r in table if not re.match(r"^\|[-:| ]+\|$", r)]
        h = "".join(f"<th>{inline(c.strip())}</th>" for c in rows[0])
        body = "".join(
            "<tr>" + "".join(f"<td>{inline(c.strip())}</td>" for c in r) + "</tr>" for r in rows[1:]
        )
        out.append(
            f'<div class="tw"><table><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table></div>'
        )
        table.clear()

    for line in md.splitlines():
        if line.startswith("|"):
            table.append(line)
            continue
        flush()
        if line.startswith("#"):
            lvl = min(len(line) - len(line.lstrip("#")) + 1, 4)
            out.append(f"<h{lvl}>{inline(line.lstrip('#').strip())}</h{lvl}>")
        elif line.strip():
            out.append(f"<p>{inline(line.strip())}</p>")
    flush()
    return "\n".join(out)


CSS = """
:root{--bg:#fbfbf9;--fg:#1d1f22;--muted:#5b6068;--line:#dcdcd6;--card:#ffffff;--accent:#0f6e5f}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#15171a;--fg:#e7e7e3;
--muted:#a3a7ad;--line:#33363b;--card:#1d2024;--accent:#5cc7b2}}
:root[data-theme="dark"]{--bg:#15171a;--fg:#e7e7e3;--muted:#a3a7ad;--line:#33363b;--card:#1d2024;
--accent:#5cc7b2}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:28px;margin:8px 0 4px}
h2{font-size:20px;margin:36px 0 8px;border-top:1px solid var(--line);
padding-top:20px}h3,h4{font-size:16px;margin:20px 0 6px}
p{margin:8px 0}a{color:var(--accent)}code{font-size:13px}
.muted{color:var(--muted)}
.note{border-left:3px solid var(--accent);padding:6px 12px;background:var(--card)}
.tw{overflow-x:auto;margin:10px 0}table{border-collapse:collapse;font-size:13.5px;min-width:100%}
th,td{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}
th{font-weight:600}td{font-variant-numeric:tabular-nums}
.imgs{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}
figure{margin:0;background:var(--card);border:1px solid var(--line);padding:8px}
figure img{width:100%;image-rendering:pixelated;display:block}
figcaption{font-size:13px;color:var(--muted);
margin-top:6px}
"""

IMAGES = [
    ("ct_zoom_pan_measure", "CT (pydicom CT_small): zoom 2.5, pan, W 400 L 40, measurement in mm"),
    ("axial_slice3_measure", "Synthetic axial phantom, slice 3: 52 rows x 0.8 mm = 41.6 mm"),
    ("sagittal_slice1", "Synthetic sagittal phantom: labels H/F/A/P from ImageOrientationPatient"),
    ("mr_default", "MR (pydicom MR_small): window from WindowCenter/WindowWidth tags"),
    ("ct_contrast", "CT with contrast x2 and brightness +50 from the default window"),
    ("mono1_default", "MONOCHROME1 ramp: displayed inverted"),
]


def main() -> int:
    OUT.mkdir(exist_ok=True)
    (OUT / "img").mkdir(exist_ok=True)
    for name, _ in IMAGES:
        shutil.copy(ROOT / f"docs/img/{name}.png", OUT / f"img/{name}.png")
    sec = render_all()
    digest_md = (ROOT / "reports/sample/digest-sample.md").read_text(encoding="utf-8")
    lines = digest_md.splitlines()
    # keep the digest head and the first 15 item rows
    cut, rows = [], 0
    for line in lines:
        if line.startswith("| 20"):
            rows += 1
            if rows > 15:
                continue
        cut.append(line)
    digest_html = md_to_html("\n".join(cut).replace("# Viewer vigilance digest", "### Digest"))
    figs = "".join(
        f'<figure><img src="img/{n}.png" alt="{html.escape(c)}"><figcaption>{html.escape(c)}'
        "</figcaption></figure>"
        for n, c in IMAGES
    )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Viewer Vigilance Kit</title><style>{CSS}</style></head>
<body><main>
<h1>viewer-vigilance-kit</h1>
<p class="muted">Release support for a medical imaging viewer: public vigilance monitoring
(openFDA MAUDE, openFDA recalls, BfArM field safety notices) plus a tested minimal DICOM viewer
core with a release-candidate gate. Code, tests and workflows:
<a href="{REPO}">{REPO}</a></p>
<p class="note">Not a medical device, not validated for clinical use. Every number on this page
is produced by a script in the repository and saved to <code>results/*.json</code>.
Labels used for evaluation are agency weak labels, not hand labels.</p>

<h2>Viewer core: rendered examples</h2>
<div class="imgs">{figs}</div>

<h2>Test suite strength: planted viewer defects</h2>
<p>15 realistic viewer bugs, switched on one at a time; a tier "catches" a defect if any of its
tests fail. The same author wrote defects and tests (see caveat in the README).</p>
{md_to_html(sec["mutants"])}
<p>{inline(sec["tests"])}</p>

<h2>Vigilance monitor: sources</h2>
<h3>FDA product codes (verified via openFDA classification)</h3>
{md_to_html(sec["product_codes"])}
<h3>Evaluation corpus</h3>
{md_to_html(sec["fetch"])}

<h2>Tagger vs agency weak labels</h2>
<p>BfArM: rule flag on the notice title vs the agency's Produktgruppe. MAUDE: category rules on
the narrative vs FDA product_problems terms. 50/50 split by id hash; rules tuned on dev only.</p>
{md_to_html(sec["tagger"])}

<h2>Weekly digest sample</h2>
{md_to_html(sec["digest"])}
{digest_html}

<p class="muted">Source: <a href="{REPO}">{REPO}</a> (MIT). Author: Pavan Yadava Annappa.</p>
</main></body></html>
"""
    (OUT / "index.html").write_text(page, encoding="utf-8")
    (OUT / "README.md").write_text(
        "---\ntitle: Viewer Vigilance Kit\nemoji: 🩻\ncolorFrom: green\ncolorTo: gray\n"
        "sdk: static\npinned: false\nlicense: mit\n---\n\n"
        f"Static results page for {REPO}\n",
        encoding="utf-8",
    )
    print("wrote", OUT / "index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
