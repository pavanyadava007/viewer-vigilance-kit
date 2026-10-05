"""dicomview: render a DICOM image or series slice to PNG with overlays."""

from __future__ import annotations

import argparse
import json

from .core import Viewport, adjust_window, default_window, load_series
from .render import View, overlay_spec, render


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dicomview", description=__doc__)
    ap.add_argument("path", help="DICOM file or directory holding one series")
    ap.add_argument("-o", "--out", required=True, help="output PNG")
    ap.add_argument("--slice", type=int, default=None, help="slice index (default: middle)")
    ap.add_argument("--size", type=int, nargs=2, default=None, metavar=("W", "H"))
    ap.add_argument("--zoom", type=float, default=1.0)
    ap.add_argument("--pan", type=float, nargs=2, default=(0.0, 0.0), metavar=("DX", "DY"))
    ap.add_argument("--window", type=float, nargs=2, default=None, metavar=("CENTER", "WIDTH"))
    ap.add_argument("--brightness", type=float, default=0.0)
    ap.add_argument("--contrast", type=float, default=1.0)
    ap.add_argument(
        "--measure", type=float, nargs=4, default=None, metavar=("R1", "C1", "R2", "C2")
    )
    ap.add_argument("--print-overlay", action="store_true", help="print overlay spec as JSON")
    a = ap.parse_args(argv)
    slices = load_series(a.path)
    idx = len(slices) // 2 if a.slice is None else a.slice
    s = slices[idx]
    h, w = s.pixels.shape
    vp = Viewport(*(a.size or (w, h)), zoom=a.zoom, pan=tuple(a.pan))
    c, ww = a.window or default_window(s)
    c, ww = adjust_window(c, ww, a.brightness, a.contrast)
    m = None
    if a.measure:
        m = ((a.measure[0], a.measure[1]), (a.measure[2], a.measure[3]))
    view = View(vp, (c, ww), m)
    render(s, view).save(a.out)
    if a.print_overlay:
        print(json.dumps(overlay_spec(s, view), indent=1))
    print(f"wrote {a.out} ({len(slices)} slice(s), shown index {idx})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
