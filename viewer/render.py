"""Rendering: windowed viewport image plus an overlay described as plain data.

The overlay is a list of primitives (text / line) so golden tests can compare it
exactly without depending on font rasterisation; `draw()` turns it into pixels.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .core import (
    Slice,
    Viewport,
    default_window,
    distance_mm,
    image_to_screen,
    orientation_labels,
    render_viewport,
    to_display,
)


@dataclass
class View:
    vp: Viewport
    window: tuple[float, float] | None = None  # None = default window
    measure: tuple[tuple[float, float], tuple[float, float]] | None = None  # (row, col) pts


def image_layer(s: Slice, view: View) -> np.ndarray:
    c, w = view.window or default_window(s)
    return render_viewport(to_display(s, c, w), view.vp)


def overlay_spec(s: Slice, view: View) -> list[dict]:
    vp = view.vp
    c, w = view.window or default_window(s)
    spec: list[dict] = []
    if s.iop is not None:
        lab = orientation_labels(s.iop)
        spec += [
            {"kind": "text", "xy": [vp.width // 2 - 4, 4], "text": lab["top"]},
            {"kind": "text", "xy": [vp.width // 2 - 4, vp.height - 16], "text": lab["bottom"]},
            {"kind": "text", "xy": [4, vp.height // 2 - 6], "text": lab["left"]},
            {"kind": "text", "xy": [vp.width - 16, vp.height // 2 - 6], "text": lab["right"]},
        ]
    spec.append(
        {"kind": "text", "xy": [4, 4], "text": f"W {w:g} L {c:g}  Z {vp.zoom:g}x"},
    )
    if view.measure is not None:
        p1, p2 = view.measure
        shape = s.pixels.shape
        # measure between pixel centres
        a = image_to_screen(p1[0] + 0.5, p1[1] + 0.5, vp, shape)
        b = image_to_screen(p2[0] + 0.5, p2[1] + 0.5, vp, shape)
        d = distance_mm(p1, p2, s.spacing)
        spec.append(
            {"kind": "line", "xy": [round(a[0], 2), round(a[1], 2), round(b[0], 2), round(b[1], 2)]}
        )
        spec.append({"kind": "text", "xy": [4, vp.height - 16], "text": f"{d:.1f} mm"})
    return spec


def draw(layer: np.ndarray, spec: list[dict]) -> Image.Image:
    img = Image.fromarray(layer, mode="L").convert("RGB")
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    for p in spec:
        if p["kind"] == "text":
            x, y = p["xy"]
            d.text((x + 1, y + 1), p["text"], fill=(0, 0, 0), font=font)
            d.text((x, y), p["text"], fill=(255, 220, 0), font=font)
        elif p["kind"] == "line":
            d.line(p["xy"], fill=(0, 255, 120), width=1)
    return img


def render(s: Slice, view: View) -> Image.Image:
    return draw(image_layer(s, view), overlay_spec(s, view))
