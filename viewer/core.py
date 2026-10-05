"""Viewer core: loading, slice sorting, rescale, window/level, viewport, orientation, measure.

Coordinate conventions
- Image points are (row, col); pixel (r, c) covers [r, r+1) x [c, c+1), centre at +0.5.
- Patient coordinates are DICOM LPS: +x = patient Left, +y = Posterior, +z = Head.
- ImageOrientationPatient = row direction cosines (direction of increasing column)
  followed by column direction cosines (direction of increasing row).
- PixelSpacing = (spacing between adjacent rows, spacing between adjacent columns) in mm.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pydicom
from pydicom.multival import MultiValue

from ._defects import active


@dataclass
class Slice:
    raw: np.ndarray
    pixels: np.ndarray  # modality values (after rescale), float64
    spacing: tuple[float, float] | None = None
    iop: np.ndarray | None = None
    ipp: np.ndarray | None = None
    instance: int | None = None
    window: tuple[float, float] | None = None  # (center, width) from tags
    photometric: str = "MONOCHROME2"
    path: str = ""
    meta: dict = field(default_factory=dict)


# ---------------------------------------------------------------- pixel values


def apply_rescale(raw: np.ndarray, slope: float = 1.0, intercept: float = 0.0) -> np.ndarray:
    """Modality LUT: value = raw * slope + intercept, computed in float64."""
    if active("ignore_rescale_intercept"):
        intercept = 0.0
    if active("rescale_in_storage_dtype"):
        out = raw * np.asarray(slope).astype(raw.dtype) + np.asarray(intercept).astype(raw.dtype)
        return out.astype(np.float64)
    return raw.astype(np.float64) * float(slope) + float(intercept)


def _first(v) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, MultiValue | list | tuple):
        if active("multivalue_window_ignored"):
            return None
        return float(v[0]) if len(v) else None
    return float(v)


def window_from_tags(center, width) -> tuple[float, float] | None:
    """WindowCenter/WindowWidth tags -> (center, width); multi-valued: first pair."""
    c, w = _first(center), _first(width)
    if c is None or w is None or w < 1:
        return None
    return c, w


def default_window(s: Slice) -> tuple[float, float]:
    """Window from the tags, else min/max of the modality values."""
    if s.window is not None:
        return s.window
    lo, hi = float(np.min(s.pixels)), float(np.max(s.pixels))
    return (lo + hi) / 2.0, max(hi - lo, 1.0)


def apply_window(values: np.ndarray, center: float, width: float) -> np.ndarray:
    """DICOM linear VOI LUT (PS3.3 C.11.2.1.2.1) to uint8 0..255."""
    c, w = center - 0.5, width - 1.0
    if active("window_off_by_one"):
        c, w = center, width
    x = np.asarray(values, dtype=np.float64)
    if w <= 0:
        return np.where(x > c, 255, 0).astype(np.uint8)
    y = np.clip((x - c) / w + 0.5, 0.0, 1.0)
    return np.floor(y * 255.0 + 0.5).astype(np.uint8)


def to_display(s: Slice, center: float, width: float) -> np.ndarray:
    """Window a slice and apply photometric interpretation (MONOCHROME1 is inverted)."""
    out = apply_window(s.pixels, center, width)
    if s.photometric == "MONOCHROME1" and not active("ignore_monochrome1"):
        out = 255 - out
    return out


def adjust_window(
    center: float, width: float, brightness: float = 0.0, contrast: float = 1.0
) -> tuple[float, float]:
    """Contrast adjustment: contrast > 1 narrows the window, brightness > 0 lowers the centre."""
    if contrast <= 0:
        raise ValueError("contrast must be > 0")
    new_w = width * contrast if active("contrast_inverted") else width / contrast
    return center - brightness, max(new_w, 1.0)


# ---------------------------------------------------------------- loading / sorting


def read_slice(path: str | Path) -> Slice:
    ds = pydicom.dcmread(str(path))
    raw = ds.pixel_array
    slope = float(ds.get("RescaleSlope", 1) or 1)
    intercept = float(ds.get("RescaleIntercept", 0) or 0)
    ps = ds.get("PixelSpacing")
    iop = ds.get("ImageOrientationPatient")
    ipp = ds.get("ImagePositionPatient")
    inst = ds.get("InstanceNumber")
    return Slice(
        raw=raw,
        pixels=apply_rescale(raw, slope, intercept),
        spacing=(float(ps[0]), float(ps[1])) if ps else None,
        iop=np.array([float(v) for v in iop]) if iop else None,
        ipp=np.array([float(v) for v in ipp]) if ipp else None,
        instance=int(inst) if inst not in (None, "") else None,
        window=window_from_tags(ds.get("WindowCenter"), ds.get("WindowWidth")),
        photometric=str(ds.get("PhotometricInterpretation", "MONOCHROME2")),
        path=str(path),
        meta={
            "modality": str(ds.get("Modality", "")),
            "rows": int(ds.Rows),
            "cols": int(ds.Columns),
        },
    )


def slice_normal(iop: Sequence[float]) -> np.ndarray:
    row, col = np.asarray(iop[:3], float), np.asarray(iop[3:], float)
    return np.cross(row, col)


def sort_slices(slices: list[Slice]) -> list[Slice]:
    """Sort by position along the slice normal (ascending); fall back to InstanceNumber."""
    if active("sort_by_filename"):
        return sorted(slices, key=lambda s: Path(s.path).name)
    if all(s.ipp is not None and s.iop is not None for s in slices):
        if active("sort_by_z_only"):
            return sorted(slices, key=lambda s: float(s.ipp[2]))
        n = slice_normal(slices[0].iop)
        return sorted(slices, key=lambda s: float(np.dot(s.ipp, n)))
    return sorted(slices, key=lambda s: (s.instance is None, s.instance or 0))


def load_series(paths: Iterable[str | Path] | str | Path) -> list[Slice]:
    """Load a directory (all files) or a list of files and return sorted slices."""
    if isinstance(paths, str | Path) and Path(paths).is_dir():
        files = [p for p in Path(paths).iterdir() if p.is_file() and not p.name.startswith(".")]
    elif isinstance(paths, str | Path):
        files = [Path(paths)]
    else:
        files = [Path(p) for p in paths]
    # os-independent load order (file system order differs between machines)
    files.sort(key=lambda p: p.name)
    return sort_slices([read_slice(f) for f in files])


def slice_positions(slices: list[Slice]) -> list[float]:
    """Signed distance of each slice along the normal of the first slice (mm)."""
    n = slice_normal(slices[0].iop)
    return [float(np.dot(s.ipp, n)) for s in slices]


# ---------------------------------------------------------------- orientation

_AXES = (("L", "R"), ("P", "A"), ("H", "F"))  # (+, -) for x, y, z in LPS


def direction_letters(v: Sequence[float], threshold: float = 0.25) -> str:
    """Patient direction letters for a vector, strongest component first."""
    axes = _AXES
    if active("flip_lr_letter"):
        axes = (("R", "L"), *_AXES[1:])
    comps = sorted(range(3), key=lambda i: -abs(v[i]))
    return "".join(axes[i][0 if v[i] > 0 else 1] for i in comps if abs(v[i]) >= threshold)


def orientation_labels(iop: Sequence[float]) -> dict[str, str]:
    """Letters for the four screen edges of an unrotated, unflipped display."""
    row, col = np.asarray(iop[:3], float), np.asarray(iop[3:], float)
    top, bottom = direction_letters(-col), direction_letters(col)
    if active("top_bottom_labels_swapped"):
        top, bottom = bottom, top
    return {
        "right": direction_letters(row),
        "left": direction_letters(-row),
        "top": top,
        "bottom": bottom,
    }


# ---------------------------------------------------------------- measurement


def distance_mm(
    p1: tuple[float, float], p2: tuple[float, float], spacing: tuple[float, float] | None
) -> float:
    """Euclidean distance between two (row, col) image points in mm."""
    dr, dc = p2[0] - p1[0], p2[1] - p1[1]
    if spacing is None:
        raise ValueError("no PixelSpacing: cannot measure in mm")
    sr, sc = spacing
    if active("swap_pixel_spacing"):
        sr, sc = sc, sr
    if active("measurement_ignores_spacing"):
        sr, sc = 1.0, 1.0
    return math.hypot(dr * sr, dc * sc)


# ---------------------------------------------------------------- viewport


@dataclass
class Viewport:
    width: int
    height: int
    zoom: float = 1.0
    pan: tuple[float, float] = (0.0, 0.0)  # screen pixels (dx right, dy down)


def _pan(vp: Viewport) -> tuple[float, float]:
    px, py = vp.pan
    return (-px, -py) if active("pan_sign_flipped") else (px, py)


def image_to_screen(
    row: float, col: float, vp: Viewport, shape: tuple[int, int]
) -> tuple[float, float]:
    """Continuous image (row, col) -> screen (x, y). Zoom is about the image centre."""
    px, py = _pan(vp)
    if active("zoom_about_origin"):
        return col * vp.zoom + px, row * vp.zoom + py
    x = (col - shape[1] / 2.0) * vp.zoom + vp.width / 2.0 + px
    y = (row - shape[0] / 2.0) * vp.zoom + vp.height / 2.0 + py
    return x, y


def screen_to_image(
    x: float, y: float, vp: Viewport, shape: tuple[int, int]
) -> tuple[float, float]:
    px, py = _pan(vp)
    if active("zoom_about_origin"):
        return (y - py) / vp.zoom, (x - px) / vp.zoom
    col = (x - vp.width / 2.0 - px) / vp.zoom + shape[1] / 2.0
    row = (y - vp.height / 2.0 - py) / vp.zoom + shape[0] / 2.0
    return row, col


def render_viewport(img: np.ndarray, vp: Viewport, fill: int = 0) -> np.ndarray:
    """Nearest-neighbour resample of a 2D uint8 image into the viewport."""
    ys = np.arange(vp.height) + 0.5
    xs = np.arange(vp.width) + 0.5
    gx, gy = np.meshgrid(xs, ys)
    rows, cols = screen_to_image(gx, gy, vp, img.shape)
    r = np.floor(rows).astype(int)
    c = np.floor(cols).astype(int)
    ok = (r >= 0) & (r < img.shape[0]) & (c >= 0) & (c < img.shape[1])
    out = np.full((vp.height, vp.width), fill, dtype=img.dtype)
    out[ok] = img[r[ok], c[ok]]
    if active("vertical_flip_render"):
        out = out[::-1]
    return out
