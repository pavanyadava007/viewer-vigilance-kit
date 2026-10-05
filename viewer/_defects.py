"""Planted defects for measuring test-suite strength (mutation testing).

Each defect is a realistic viewer bug that can be switched on with the environment
variable VIEWER_DEFECT=<name>. With the variable unset (the normal case) every
`active()` call returns False and the code paths are the correct ones.
scripts/run_mutants.py switches them on one at a time and records which test tier
fails.
"""

from __future__ import annotations

import os

DEFECTS: dict[str, str] = {
    "ignore_rescale_intercept": "Rescale Intercept ignored (CT values off by +1024 HU)",
    "rescale_in_storage_dtype": "rescale done in uint16 storage dtype, negative HU wrap around",
    "swap_pixel_spacing": "row and column PixelSpacing swapped in measurements",
    "measurement_ignores_spacing": "distance reported in pixels instead of mm",
    "flip_lr_letter": "patient x axis mapped to R instead of L in orientation labels",
    "top_bottom_labels_swapped": "top and bottom orientation labels swapped",
    "sort_by_filename": "series sorted by file name instead of slice position",
    "sort_by_z_only": "series sorted by z coordinate instead of position along the normal",
    "window_off_by_one": "window uses width instead of width-1 and centre instead of centre-0.5",
    "multivalue_window_ignored": "multi-valued WindowCenter/Width ignored, falls back to min/max",
    "ignore_monochrome1": "MONOCHROME1 images not inverted",
    "contrast_inverted": "contrast factor widens the window instead of narrowing it",
    "zoom_about_origin": "zoom anchored at the top-left corner instead of the image centre",
    "pan_sign_flipped": "pan moves the image opposite to the drag direction",
    "vertical_flip_render": "rendered rows written bottom-up",
}


def active(name: str) -> bool:
    if name not in DEFECTS:
        raise KeyError(name)
    return os.environ.get("VIEWER_DEFECT", "") == name
