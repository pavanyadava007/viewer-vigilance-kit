"""Tier 2: unit tests with hand-checked expected values."""

from __future__ import annotations

import math

import numpy as np
import pytest
from pydicom.multival import MultiValue

from viewer.core import (
    Slice,
    Viewport,
    adjust_window,
    apply_rescale,
    apply_window,
    default_window,
    direction_letters,
    distance_mm,
    image_to_screen,
    load_series,
    orientation_labels,
    render_viewport,
    screen_to_image,
    slice_normal,
    slice_positions,
    sort_slices,
    to_display,
    window_from_tags,
)

pytestmark = pytest.mark.unit


# ------------------------------------------------------------ rescale


def test_rescale_uint16_negative_intercept():
    raw = np.array([0, 24, 1024, 2048], dtype=np.uint16)
    assert apply_rescale(raw, 1, -1024).tolist() == [-1024, -1000, 0, 1024]


def test_rescale_slope_and_int16():
    raw = np.array([-5, 7], dtype=np.int16)
    assert apply_rescale(raw, 2.0, -10).tolist() == [-20.0, 4.0]


def test_ct_small_hu_range(ct_small):
    # CT_small.dcm: raw int16 min 128, max 2191, RescaleIntercept -1024, slope 1
    s = load_series(ct_small)[0]
    assert s.pixels.min() == 128 - 1024
    assert s.pixels.max() == 2191 - 1024


def test_phantom_hu_values(axial_dir):
    s = load_series(axial_dir)[0]
    assert s.pixels[0, 0] == -1000  # air (stored 24, intercept -1024)
    assert s.pixels[32, 32] == 700  # bone core
    assert s.pixels[22, 46] == 300  # left marker


# ------------------------------------------------------------ window / level


def test_window_from_tags_multivalue_takes_first():
    wc = MultiValue(float, [40, -600])
    ww = MultiValue(float, [400, 1500])
    assert window_from_tags(wc, ww) == (40.0, 400.0)


def test_window_from_tags_single_and_missing():
    assert window_from_tags(600, 1600) == (600.0, 1600.0)
    assert window_from_tags(None, 400) is None
    assert window_from_tags(40, 0) is None


def test_phantom_window_from_multivalued_tags(axial_dir):
    s = load_series(axial_dir)[0]
    assert default_window(s) == (40.0, 400.0)


def test_mr_small_window_tags(mr_small):
    assert default_window(load_series(mr_small)[0]) == (600.0, 1600.0)


def test_default_window_min_max_fallback(ct_small):
    # no window tags in CT_small: centre (-896 + 1167) / 2, width 1167 - (-896)
    assert default_window(load_series(ct_small)[0]) == (135.5, 2063.0)


def test_apply_window_hand_values():
    # centre 40, width 400 -> c' = 39.5, w' = 399; bounds -160 and 239.5
    x = np.array([-1000, -160, 39.5, 139.25, 239.5, 3000])
    # 39.5 -> 0.5 * 255 = 127.5 -> 128;  139.25 -> 0.75 * 255 = 191.25 -> 191
    assert apply_window(x, 40, 400).tolist() == [0, 0, 128, 191, 255, 255]


def test_apply_window_width_one_is_threshold():
    assert apply_window(np.array([-1.0, 0.0, 1.0]), 0, 1).tolist() == [0, 255, 255]


def test_monochrome1_inverted(mono1):
    s = load_series(mono1)[0]
    out = to_display(s, *default_window(s))
    # raw 0 -> 0 -> inverted 255 ; raw 252 -> (124.5/255 + .5) * 255 = 252 -> inverted 3
    assert out[0, 0] == 255
    assert out[0, -1] == 3


def test_adjust_window_contrast_and_brightness():
    assert adjust_window(40, 400, contrast=2.0) == (40, 200.0)
    assert adjust_window(40, 400, brightness=10) == (30, 400.0)
    with pytest.raises(ValueError):
        adjust_window(40, 400, contrast=0)


# ------------------------------------------------------------ sorting


def test_slice_normal():
    assert slice_normal([1, 0, 0, 0, 1, 0]).tolist() == [0, 0, 1]
    assert slice_normal([0, 1, 0, 0, 0, -1]).tolist() == [-1, 0, 0]


def test_sort_axial_phantom(axial_dir):
    sl = load_series(axial_dir)
    assert [s.instance for s in sl] == list(range(1, 9))
    assert slice_positions(sl) == pytest.approx([-10 + 2.5 * i for i in range(8)])


def test_sort_sagittal_uses_normal_not_z(sagittal_dir):
    # normal (-1,0,0): ascending projection = descending x = instances 5..1
    sl = load_series(sagittal_dir)
    assert [s.instance for s in sl] == [5, 4, 3, 2, 1]


def test_sort_real_ct5n_series(ct5n_dir):
    # pydicom CT5N: InstanceNumber 6..10 have z 8.76 .. -1.24 (decreasing)
    sl = load_series(ct5n_dir)
    assert [s.instance for s in sl] == [10, 9, 8, 7, 6]


def test_sort_fallback_instance_number():
    sl = [Slice(np.zeros((1, 1)), np.zeros((1, 1)), instance=i, path=f"{9 - i}") for i in (3, 1, 2)]
    assert [s.instance for s in sort_slices(sl)] == [1, 2, 3]


# ------------------------------------------------------------ orientation


@pytest.mark.parametrize(
    "vec,letters",
    [
        ((1, 0, 0), "L"),
        ((-1, 0, 0), "R"),
        ((0, 1, 0), "P"),
        ((0, -1, 0), "A"),
        ((0, 0, 1), "H"),
        ((0, 0, -1), "F"),
        ((0.8, 0.6, 0), "LP"),
        ((-0.1, -0.5, 0.86), "HA"),
    ],
)
def test_direction_letters(vec, letters):
    assert direction_letters(vec) == letters


def test_orientation_labels_axial():
    lab = orientation_labels([1, 0, 0, 0, 1, 0])
    assert lab == {"right": "L", "left": "R", "top": "A", "bottom": "P"}


def test_orientation_labels_sagittal():
    lab = orientation_labels([0, 1, 0, 0, 0, -1])
    assert lab == {"right": "P", "left": "A", "top": "H", "bottom": "F"}


# ------------------------------------------------------------ measurement


def test_distance_mm_anisotropic():
    # 3 rows * 0.8 mm = 2.4 mm, 4 cols * 0.5 mm = 2.0 mm -> sqrt(2.4^2 + 2.0^2)
    assert distance_mm((0, 0), (3, 4), (0.8, 0.5)) == pytest.approx(math.hypot(2.4, 2.0))


def test_distance_mm_isotropic_and_missing():
    assert distance_mm((0, 0), (3, 4), (1.0, 1.0)) == pytest.approx(5.0)
    with pytest.raises(ValueError):
        distance_mm((0, 0), (1, 1), None)


def test_distance_on_phantom(axial_dir):
    s = load_series(axial_dir)[0]
    assert distance_mm((6, 32), (58, 32), s.spacing) == pytest.approx(52 * 0.8)


# ------------------------------------------------------------ viewport


def test_viewport_identity():
    img = np.arange(12, dtype=np.uint8).reshape(3, 4)
    assert np.array_equal(render_viewport(img, Viewport(4, 3)), img)


def test_viewport_zoom_two_is_centre_crop():
    img = np.arange(16, dtype=np.uint8).reshape(4, 4)
    out = render_viewport(img, Viewport(4, 4, zoom=2.0))
    expected = np.array([[5, 5, 6, 6], [5, 5, 6, 6], [9, 9, 10, 10], [9, 9, 10, 10]])
    assert np.array_equal(out, expected)


def test_image_to_screen_zoom_about_centre():
    vp = Viewport(4, 4, zoom=2.0)
    assert image_to_screen(2, 2, vp, (4, 4)) == (2.0, 2.0)
    assert image_to_screen(0, 0, vp, (4, 4)) == (-2.0, -2.0)


def test_pan_moves_image_with_drag():
    vp = Viewport(10, 10, pan=(3, -2))
    assert image_to_screen(5, 5, vp, (10, 10)) == (8.0, 3.0)
    img = np.zeros((10, 10), np.uint8)
    img[5, 5] = 255
    out = render_viewport(img, vp)
    assert out[3, 8] == 255


def test_screen_image_roundtrip():
    vp = Viewport(37, 23, zoom=1.7, pan=(4.5, -3.25))
    r, c = screen_to_image(*image_to_screen(11.2, 7.9, vp, (30, 20)), vp, (30, 20))
    assert (r, c) == pytest.approx((11.2, 7.9))
