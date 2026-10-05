"""Tier 1: smoke tests. Does it load and render without crashing, with sane shapes."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from viewer.cli import main as cli_main
from viewer.core import Viewport, load_series
from viewer.render import View, render

pytestmark = pytest.mark.smoke


def test_load_ct_small(ct_small):
    s = load_series(ct_small)[0]
    assert s.pixels.shape == (128, 128)
    assert s.pixels.dtype == np.float64


def test_load_mr_small(mr_small):
    s = load_series(mr_small)[0]
    assert s.pixels.shape == (64, 64)


def test_load_phantom_series(axial_dir, sagittal_dir):
    assert len(load_series(axial_dir)) == 8
    assert len(load_series(sagittal_dir)) == 5


def test_render_returns_rgb_of_viewport_size(ct_small):
    s = load_series(ct_small)[0]
    img = render(s, View(Viewport(100, 80, zoom=2.0, pan=(5, 5)), None, ((10, 10), (50, 50))))
    assert img.size == (100, 80)
    assert img.mode == "RGB"


def test_cli_writes_png(tmp_path, ct_small):
    out = tmp_path / "x.png"
    rc = cli_main([ct_small, "-o", str(out), "--zoom", "2", "--measure", "1", "1", "20", "20"])
    assert rc == 0
    assert Image.open(out).size == (128, 128)


def test_cli_series_and_contrast(tmp_path, axial_dir):
    out = tmp_path / "s.png"
    assert cli_main([str(axial_dir), "-o", str(out), "--contrast", "2", "--brightness", "10"]) == 0
    assert out.stat().st_size > 0
