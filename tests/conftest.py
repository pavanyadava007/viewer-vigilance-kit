from __future__ import annotations

from pathlib import Path

import pytest
from pydicom.data import get_testdata_file

HERE = Path(__file__).parent
DATA = HERE / "data"
FIX = HERE / "fixtures"


@pytest.fixture(scope="session")
def ct_small() -> str:
    return get_testdata_file("CT_small.dcm")


@pytest.fixture(scope="session")
def mr_small() -> str:
    return get_testdata_file("MR_small.dcm")


@pytest.fixture(scope="session")
def ct5n_dir() -> Path:
    """Real 5-slice CT series bundled with pydicom (dicomdirtests/98892001/CT5N)."""
    return Path(get_testdata_file("CT_small.dcm")).parent / "dicomdirtests/98892001/CT5N"


@pytest.fixture(scope="session")
def axial_dir() -> Path:
    return DATA / "phantom_axial"


@pytest.fixture(scope="session")
def sagittal_dir() -> Path:
    return DATA / "phantom_sagittal"


@pytest.fixture(scope="session")
def mono1() -> Path:
    return DATA / "mono1.dcm"
