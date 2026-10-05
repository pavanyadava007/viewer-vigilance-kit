"""Tier 3: golden-image regression (exact pixel layer + exact overlay spec)."""

from __future__ import annotations

import json

import numpy as np
import pytest
from PIL import Image

from tests.scenarios import GOLDEN, scenarios
from viewer.render import image_layer, overlay_spec

pytestmark = pytest.mark.golden

NAMES = sorted(p.name.removesuffix(".overlay.json") for p in GOLDEN.glob("*.overlay.json"))


@pytest.fixture(scope="module")
def built():
    return scenarios()


def test_golden_set_complete(built):
    assert sorted(built) == NAMES


@pytest.mark.parametrize("name", NAMES)
def test_golden_pixels(built, name):
    s, view = built[name]
    expected = np.asarray(Image.open(GOLDEN / f"{name}.png"))
    got = image_layer(s, view)
    assert got.shape == expected.shape
    n_diff = int(np.count_nonzero(got != expected))
    assert n_diff == 0, f"{n_diff} pixels differ from golden {name}"


@pytest.mark.parametrize("name", NAMES)
def test_golden_overlay(built, name):
    s, view = built[name]
    expected = json.loads((GOLDEN / f"{name}.overlay.json").read_text())
    assert overlay_spec(s, view) == expected
