"""Golden-image scenarios shared by tests/test_viewer_golden.py and scripts/make_goldens.py."""

from __future__ import annotations

from pathlib import Path

from pydicom.data import get_testdata_file

from viewer.core import Viewport, adjust_window, default_window, load_series
from viewer.render import View

DATA = Path(__file__).parent / "data"
GOLDEN = Path(__file__).parent / "golden"


def _ct():
    return load_series(get_testdata_file("CT_small.dcm"))[0]


def scenarios() -> dict:
    """name -> (slice, View). Built lazily so defects (env var) apply at call time."""
    ct = _ct()
    mr = load_series(get_testdata_file("MR_small.dcm"))[0]
    ax = load_series(DATA / "phantom_axial")
    sag = load_series(DATA / "phantom_sagittal")
    mono = load_series(DATA / "mono1.dcm")[0]
    c, w = default_window(ct)
    return {
        "ct_default": (ct, View(Viewport(128, 128))),
        "ct_zoom_pan_measure": (
            ct,
            View(Viewport(160, 120, zoom=2.5, pan=(15, -10)), (40, 400), ((30, 30), (90, 100))),
        ),
        "ct_contrast": (ct, View(Viewport(128, 128), adjust_window(c, w, 50, 2.0))),
        "mr_default": (mr, View(Viewport(96, 96, zoom=1.5))),
        "axial_slice3_measure": (
            ax[3],
            View(Viewport(96, 96, zoom=1.5), None, ((6, 32), (58, 32))),
        ),
        "axial_slice6": (ax[6], View(Viewport(64, 64))),
        "sagittal_slice1": (sag[1], View(Viewport(48, 48), (500, 1000))),
        "mono1_default": (mono, View(Viewport(64, 16))),
    }
